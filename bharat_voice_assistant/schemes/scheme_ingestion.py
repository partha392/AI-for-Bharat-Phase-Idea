"""
Automated scheme ingestion from government sources.

This module provides comprehensive functionality for automatically ingesting
government scheme data from various sources including APIs, web scraping,
and structured data feeds.
"""

import logging
import asyncio
import aiohttp
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, AsyncGenerator
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET
from dataclasses import asdict

import requests
from bs4 import BeautifulSoup
import feedparser

from .models import (
    GovernmentScheme, SchemeCategory, SchemeStatus, DataSource,
    EligibilityCriteria, SchemeBenefits, ApplicationProcess,
    SchemeMetadata, IngestionResult
)
from .scheme_validator import SchemeValidator
from .scheme_categorizer import SchemeCategorizer
from ..core.config import config
from ..core.exceptions import IngestionError

logger = logging.getLogger(__name__)


class SchemeIngestionService:
    """
    Service for automated ingestion of government scheme data.
    
    Supports multiple data sources including:
    - Government APIs (MyGov, Digital India, etc.)
    - Web scraping from official portals
    - RSS/XML feeds
    - Structured data files (JSON, CSV)
    """
    
    def __init__(self):
        """Initialize the scheme ingestion service."""
        self.validator = SchemeValidator()
        self.categorizer = SchemeCategorizer()
        self.session = None
        self.ingestion_sources = self._load_ingestion_sources()
        self.rate_limits = self._load_rate_limits()
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'Bharat-Voice-Assistant/1.0'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def ingest_from_all_sources(self) -> IngestionResult:
        """
        Ingest schemes from all configured sources.
        
        Returns:
            Comprehensive ingestion result
        """
        start_time = time.time()
        total_result = IngestionResult(source="all_sources")
        
        logger.info("Starting comprehensive scheme ingestion from all sources")
        
        for source_name, source_config in self.ingestion_sources.items():
            try:
                logger.info(f"Ingesting from source: {source_name}")
                
                if source_config['type'] == 'api':
                    result = await self._ingest_from_api(source_name, source_config)
                elif source_config['type'] == 'web_scraping':
                    result = await self._ingest_from_web_scraping(source_name, source_config)
                elif source_config['type'] == 'rss_feed':
                    result = await self._ingest_from_rss_feed(source_name, source_config)
                elif source_config['type'] == 'file':
                    result = await self._ingest_from_file(source_name, source_config)
                else:
                    logger.warning(f"Unknown source type: {source_config['type']}")
                    continue
                
                # Aggregate results
                total_result.total_processed += result.total_processed
                total_result.successful_updates += result.successful_updates
                total_result.failed_updates += result.failed_updates
                total_result.new_schemes += result.new_schemes
                total_result.updated_schemes += result.updated_schemes
                total_result.validation_errors.extend(result.validation_errors)
                
                logger.info(f"Completed ingestion from {source_name}: {result.successful_updates} successful")
                
                # Respect rate limits
                await asyncio.sleep(self.rate_limits.get(source_name, 1.0))
                
            except Exception as e:
                logger.error(f"Error ingesting from source {source_name}: {str(e)}")
                total_result.failed_updates += 1
                total_result.validation_errors.append({
                    'source': source_name,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
        
        total_result.processing_time_seconds = time.time() - start_time
        
        logger.info(f"Completed comprehensive ingestion: {total_result.successful_updates} successful, "
                   f"{total_result.failed_updates} failed in {total_result.processing_time_seconds:.2f}s")
        
        return total_result
    
    async def ingest_from_source(self, source_name: str) -> IngestionResult:
        """
        Ingest schemes from a specific source.
        
        Args:
            source_name: Name of the source to ingest from
            
        Returns:
            Ingestion result for the specific source
        """
        if source_name not in self.ingestion_sources:
            raise IngestionError(f"Unknown ingestion source: {source_name}")
        
        source_config = self.ingestion_sources[source_name]
        
        if source_config['type'] == 'api':
            return await self._ingest_from_api(source_name, source_config)
        elif source_config['type'] == 'web_scraping':
            return await self._ingest_from_web_scraping(source_name, source_config)
        elif source_config['type'] == 'rss_feed':
            return await self._ingest_from_rss_feed(source_name, source_config)
        elif source_config['type'] == 'file':
            return await self._ingest_from_file(source_name, source_config)
        else:
            raise IngestionError(f"Unsupported source type: {source_config['type']}")
    
    async def _ingest_from_api(self, source_name: str, config: Dict[str, Any]) -> IngestionResult:
        """Ingest schemes from a government API."""
        start_time = time.time()
        result = IngestionResult(source=source_name)
        
        try:
            base_url = config['base_url']
            endpoints = config.get('endpoints', [])
            auth_config = config.get('authentication', {})
            
            # Setup authentication if required
            headers = {}
            if auth_config.get('type') == 'api_key':
                headers[auth_config['header']] = auth_config['key']
            elif auth_config.get('type') == 'bearer':
                headers['Authorization'] = f"Bearer {auth_config['token']}"
            
            for endpoint in endpoints:
                endpoint_url = urljoin(base_url, endpoint['path'])
                
                async with self.session.get(endpoint_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        schemes = self._parse_api_response(data, endpoint.get('parser', {}))
                        
                        for scheme_data in schemes:
                            try:
                                scheme = self._create_scheme_from_data(scheme_data, DataSource.GOVERNMENT_API, endpoint_url)
                                
                                # Validate scheme
                                is_valid, errors = self.validator.validate_scheme(scheme)
                                if is_valid:
                                    # This would normally save to database
                                    result.successful_updates += 1
                                    result.new_schemes += 1
                                else:
                                    result.failed_updates += 1
                                    result.validation_errors.append({
                                        'scheme_id': scheme.scheme_id,
                                        'errors': errors,
                                        'source': source_name
                                    })
                                
                                result.total_processed += 1
                                
                            except Exception as e:
                                logger.error(f"Error processing scheme from {source_name}: {str(e)}")
                                result.failed_updates += 1
                                result.validation_errors.append({
                                    'error': str(e),
                                    'source': source_name,
                                    'data': str(scheme_data)[:200]
                                })
                    else:
                        logger.error(f"API request failed for {endpoint_url}: {response.status}")
                        result.failed_updates += 1
        
        except Exception as e:
            logger.error(f"Error in API ingestion from {source_name}: {str(e)}")
            raise IngestionError(f"API ingestion failed: {str(e)}")
        
        result.processing_time_seconds = time.time() - start_time
        return result
    
    async def _ingest_from_web_scraping(self, source_name: str, config: Dict[str, Any]) -> IngestionResult:
        """Ingest schemes through web scraping."""
        start_time = time.time()
        result = IngestionResult(source=source_name)
        
        try:
            base_url = config['base_url']
            scraping_config = config.get('scraping', {})
            
            # Get list of scheme pages
            scheme_urls = await self._discover_scheme_urls(base_url, scraping_config)
            
            for url in scheme_urls:
                try:
                    async with self.session.get(url) as response:
                        if response.status == 200:
                            html_content = await response.text()
                            scheme_data = self._extract_scheme_from_html(html_content, scraping_config)
                            
                            if scheme_data:
                                scheme = self._create_scheme_from_data(scheme_data, DataSource.WEB_SCRAPING, url)
                                
                                # Validate scheme
                                is_valid, errors = self.validator.validate_scheme(scheme)
                                if is_valid:
                                    result.successful_updates += 1
                                    result.new_schemes += 1
                                else:
                                    result.failed_updates += 1
                                    result.validation_errors.append({
                                        'scheme_id': scheme.scheme_id,
                                        'errors': errors,
                                        'source': source_name,
                                        'url': url
                                    })
                                
                                result.total_processed += 1
                        
                        # Respect rate limits for web scraping
                        await asyncio.sleep(config.get('delay', 2.0))
                        
                except Exception as e:
                    logger.error(f"Error scraping scheme from {url}: {str(e)}")
                    result.failed_updates += 1
                    result.validation_errors.append({
                        'error': str(e),
                        'source': source_name,
                        'url': url
                    })
        
        except Exception as e:
            logger.error(f"Error in web scraping from {source_name}: {str(e)}")
            raise IngestionError(f"Web scraping failed: {str(e)}")
        
        result.processing_time_seconds = time.time() - start_time
        return result
    
    async def _ingest_from_rss_feed(self, source_name: str, config: Dict[str, Any]) -> IngestionResult:
        """Ingest schemes from RSS/XML feeds."""
        start_time = time.time()
        result = IngestionResult(source=source_name)
        
        try:
            feed_url = config['feed_url']
            
            async with self.session.get(feed_url) as response:
                if response.status == 200:
                    feed_content = await response.text()
                    feed = feedparser.parse(feed_content)
                    
                    for entry in feed.entries:
                        try:
                            scheme_data = self._extract_scheme_from_feed_entry(entry, config)
                            
                            if scheme_data:
                                scheme = self._create_scheme_from_data(scheme_data, DataSource.GOVERNMENT_API, entry.link)
                                
                                # Validate scheme
                                is_valid, errors = self.validator.validate_scheme(scheme)
                                if is_valid:
                                    result.successful_updates += 1
                                    result.new_schemes += 1
                                else:
                                    result.failed_updates += 1
                                    result.validation_errors.append({
                                        'scheme_id': scheme.scheme_id,
                                        'errors': errors,
                                        'source': source_name
                                    })
                                
                                result.total_processed += 1
                        
                        except Exception as e:
                            logger.error(f"Error processing feed entry from {source_name}: {str(e)}")
                            result.failed_updates += 1
                            result.validation_errors.append({
                                'error': str(e),
                                'source': source_name,
                                'entry_title': entry.get('title', 'Unknown')
                            })
        
        except Exception as e:
            logger.error(f"Error in RSS feed ingestion from {source_name}: {str(e)}")
            raise IngestionError(f"RSS feed ingestion failed: {str(e)}")
        
        result.processing_time_seconds = time.time() - start_time
        return result
    
    async def _ingest_from_file(self, source_name: str, config: Dict[str, Any]) -> IngestionResult:
        """Ingest schemes from structured data files."""
        start_time = time.time()
        result = IngestionResult(source=source_name)
        
        try:
            file_path = config['file_path']
            file_format = config.get('format', 'json')
            
            if file_format == 'json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    schemes_data = data if isinstance(data, list) else data.get('schemes', [])
            else:
                raise IngestionError(f"Unsupported file format: {file_format}")
            
            for scheme_data in schemes_data:
                try:
                    scheme = self._create_scheme_from_data(scheme_data, DataSource.MANUAL_ENTRY, file_path)
                    
                    # Validate scheme
                    is_valid, errors = self.validator.validate_scheme(scheme)
                    if is_valid:
                        result.successful_updates += 1
                        result.new_schemes += 1
                    else:
                        result.failed_updates += 1
                        result.validation_errors.append({
                            'scheme_id': scheme.scheme_id,
                            'errors': errors,
                            'source': source_name
                        })
                    
                    result.total_processed += 1
                
                except Exception as e:
                    logger.error(f"Error processing scheme from file {source_name}: {str(e)}")
                    result.failed_updates += 1
                    result.validation_errors.append({
                        'error': str(e),
                        'source': source_name,
                        'data': str(scheme_data)[:200]
                    })
        
        except Exception as e:
            logger.error(f"Error in file ingestion from {source_name}: {str(e)}")
            raise IngestionError(f"File ingestion failed: {str(e)}")
        
        result.processing_time_seconds = time.time() - start_time
        return result
    
    def _create_scheme_from_data(self, data: Dict[str, Any], source: DataSource, source_url: str) -> GovernmentScheme:
        """Create a GovernmentScheme object from raw data."""
        # Create metadata
        metadata = SchemeMetadata(
            data_source=source,
            source_url=source_url,
            last_verified_at=datetime.now(),
            verification_status="pending"
        )
        
        # Parse eligibility criteria
        eligibility_data = data.get('eligibility_criteria', {})
        if isinstance(eligibility_data, str):
            # If it's a string, try to parse as JSON
            try:
                eligibility_data = json.loads(eligibility_data)
            except:
                eligibility_data = {}
        
        eligibility = EligibilityCriteria(
            income_limit=eligibility_data.get('income_limit'),
            age_min=eligibility_data.get('age_min'),
            age_max=eligibility_data.get('age_max'),
            location_type=eligibility_data.get('location_type'),
            gender=eligibility_data.get('gender'),
            caste_category=eligibility_data.get('caste_category'),
            education_level=eligibility_data.get('education_level'),
            employment_status=eligibility_data.get('employment_status'),
            disability_status=eligibility_data.get('disability_status'),
            additional_criteria=eligibility_data.get('additional_criteria', {})
        )
        
        # Parse benefits
        benefits_data = data.get('benefits', {})
        if isinstance(benefits_data, str):
            try:
                benefits_data = json.loads(benefits_data)
            except:
                benefits_data = {}
        
        benefits = SchemeBenefits(
            financial_assistance=benefits_data.get('financial_assistance'),
            subsidy_percentage=benefits_data.get('subsidy_percentage'),
            loan_amount=benefits_data.get('loan_amount'),
            interest_rate=benefits_data.get('interest_rate'),
            insurance_coverage=benefits_data.get('insurance_coverage'),
            training_provided=benefits_data.get('training_provided', False),
            equipment_provided=benefits_data.get('equipment_provided', False),
            description=benefits_data.get('description', ''),
            additional_benefits=benefits_data.get('additional_benefits', {})
        )
        
        # Parse application process
        process_data = data.get('application_process', {})
        if isinstance(process_data, str):
            try:
                process_data = json.loads(process_data)
            except:
                process_data = {}
        
        application_process = ApplicationProcess(
            steps=process_data.get('steps', []),
            required_documents=process_data.get('required_documents', []),
            application_fee=process_data.get('application_fee'),
            processing_time_days=process_data.get('processing_time_days'),
            application_mode=process_data.get('application_mode', []),
            contact_details=process_data.get('contact_details', {}),
            help_resources=process_data.get('help_resources', [])
        )
        
        # Determine category
        category_str = data.get('category', 'social_security')
        try:
            category = SchemeCategory(category_str)
        except ValueError:
            category = SchemeCategory.SOCIAL_SECURITY
        
        # Create scheme
        scheme = GovernmentScheme(
            scheme_id=data.get('scheme_id', ''),
            name=data.get('name', ''),
            name_hi=data.get('name_hi'),
            name_regional=data.get('name_regional', {}),
            department=data.get('department', ''),
            ministry=data.get('ministry'),
            category=category,
            subcategory=data.get('subcategory'),
            description=data.get('description', ''),
            description_hi=data.get('description_hi'),
            description_regional=data.get('description_regional', {}),
            eligibility_criteria=eligibility,
            benefits=benefits,
            application_process=application_process,
            target_states=data.get('target_states', []),
            target_districts=data.get('target_districts', []),
            status=SchemeStatus.ACTIVE,
            metadata=metadata
        )
        
        # Auto-categorize if needed
        if not data.get('category'):
            category, confidence, tags = self.categorizer.categorize_scheme(scheme)
            scheme.category = category
            scheme.metadata.tags = tags
        
        return scheme
    
    def _parse_api_response(self, data: Dict[str, Any], parser_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse API response based on configuration."""
        schemes = []
        
        # Extract schemes array from response
        schemes_path = parser_config.get('schemes_path', 'data')
        schemes_data = data
        
        for path_part in schemes_path.split('.'):
            if isinstance(schemes_data, dict):
                schemes_data = schemes_data.get(path_part, [])
            else:
                break
        
        if not isinstance(schemes_data, list):
            schemes_data = [schemes_data] if schemes_data else []
        
        # Map fields according to configuration
        field_mapping = parser_config.get('field_mapping', {})
        
        for item in schemes_data:
            scheme_data = {}
            
            for target_field, source_path in field_mapping.items():
                value = self._extract_nested_value(item, source_path)
                if value is not None:
                    scheme_data[target_field] = value
            
            if scheme_data:
                schemes.append(scheme_data)
        
        return schemes
    
    def _extract_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Extract nested value from dictionary using dot notation."""
        current = data
        
        for key in path.split('.'):
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current
    
    async def _discover_scheme_urls(self, base_url: str, config: Dict[str, Any]) -> List[str]:
        """Discover scheme URLs for web scraping."""
        urls = []
        
        # This is a simplified implementation
        # In a real system, this would use more sophisticated discovery methods
        listing_pages = config.get('listing_pages', [])
        
        for listing_page in listing_pages:
            try:
                listing_url = urljoin(base_url, listing_page)
                async with self.session.get(listing_url) as response:
                    if response.status == 200:
                        html_content = await response.text()
                        soup = BeautifulSoup(html_content, 'html.parser')
                        
                        # Extract scheme links based on CSS selectors
                        link_selector = config.get('link_selector', 'a[href*="scheme"]')
                        links = soup.select(link_selector)
                        
                        for link in links:
                            href = link.get('href')
                            if href:
                                full_url = urljoin(base_url, href)
                                urls.append(full_url)
            
            except Exception as e:
                logger.error(f"Error discovering URLs from {listing_page}: {str(e)}")
        
        return list(set(urls))  # Remove duplicates
    
    def _extract_scheme_from_html(self, html_content: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract scheme data from HTML content."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            scheme_data = {}
            
            # Extract fields based on CSS selectors
            selectors = config.get('selectors', {})
            
            for field, selector in selectors.items():
                element = soup.select_one(selector)
                if element:
                    scheme_data[field] = element.get_text(strip=True)
            
            return scheme_data if scheme_data else None
        
        except Exception as e:
            logger.error(f"Error extracting scheme from HTML: {str(e)}")
            return None
    
    def _extract_scheme_from_feed_entry(self, entry: Any, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract scheme data from RSS feed entry."""
        try:
            scheme_data = {
                'name': entry.get('title', ''),
                'description': entry.get('summary', ''),
                'scheme_id': entry.get('id', entry.get('link', '')),
            }
            
            # Extract additional fields from entry content
            field_mapping = config.get('field_mapping', {})
            for target_field, source_field in field_mapping.items():
                value = entry.get(source_field)
                if value:
                    scheme_data[target_field] = value
            
            return scheme_data if scheme_data.get('name') else None
        
        except Exception as e:
            logger.error(f"Error extracting scheme from feed entry: {str(e)}")
            return None
    
    def _load_ingestion_sources(self) -> Dict[str, Dict[str, Any]]:
        """Load ingestion source configurations."""
        # This would typically be loaded from a configuration file
        return {
            'mygov_api': {
                'type': 'api',
                'base_url': 'https://api.mygov.in/v1/',
                'endpoints': [
                    {
                        'path': 'schemes',
                        'parser': {
                            'schemes_path': 'data.schemes',
                            'field_mapping': {
                                'scheme_id': 'id',
                                'name': 'title',
                                'description': 'description',
                                'department': 'ministry',
                                'category': 'category'
                            }
                        }
                    }
                ],
                'authentication': {
                    'type': 'api_key',
                    'header': 'X-API-Key',
                    'key': getattr(config, 'MYGOV_API_KEY', '') if hasattr(config, 'MYGOV_API_KEY') else ''
                }
            },
            'digital_india_portal': {
                'type': 'web_scraping',
                'base_url': 'https://digitalindia.gov.in/',
                'scraping': {
                    'listing_pages': ['schemes/', 'initiatives/'],
                    'link_selector': 'a[href*="scheme"]',
                    'selectors': {
                        'name': 'h1.scheme-title',
                        'description': '.scheme-description',
                        'department': '.scheme-ministry',
                        'eligibility': '.eligibility-criteria'
                    }
                },
                'delay': 2.0
            },
            'pmay_schemes': {
                'type': 'file',
                'file_path': 'data/pmay_schemes.json',
                'format': 'json'
            }
        }
    
    def _load_rate_limits(self) -> Dict[str, float]:
        """Load rate limits for different sources."""
        return {
            'mygov_api': 1.0,  # 1 second between requests
            'digital_india_portal': 2.0,  # 2 seconds between requests
            'pmay_schemes': 0.1  # No significant delay for file sources
        }