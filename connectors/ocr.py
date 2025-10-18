"""
OCR connector for Enterprise AI Agent Framework.

Provides Optical Character Recognition integration for extracting text from images.
Supports multiple OCR engines and basic error handling.
"""

import json
import base64
from typing import Dict, Any, List, Optional, Union
from .base import BaseConnector, AuthenticationError, ActionError


class OCRConnector(BaseConnector):
    """
    OCR connector for text extraction from images.
    
    Supports multiple OCR engines and provides actions for
    extracting text from images and documents.
    """
    
    CONNECTOR_NAME = "ocr"
    VERSION = "1.0.0"
    DESCRIPTION = "OCR connector for text extraction from images"
    
    def __init__(self, tenant_id: Optional[str] = None, **kwargs):
        """
        Initialize the OCR connector.
        
        Args:
            tenant_id (Optional[str]): Tenant identifier
            **kwargs: Additional configuration
        """
        super().__init__(
            name=self.CONNECTOR_NAME,
            version=self.VERSION,
            tenant_id=tenant_id,
            metadata={
                'service': 'ocr',
                'engines': ['tesseract', 'google_vision', 'aws_textract', 'azure_cognitive'],
                'supported_formats': ['png', 'jpg', 'jpeg', 'tiff', 'bmp', 'pdf'],
                'languages': ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'zh', 'ja', 'ko']
            }
        )
        self._client = None
        self._api_key = None
        self._engine = None
        self._language = None
    
    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with OCR service.
        
        Args:
            credentials (Dict[str, Any]): Authentication credentials
                Expected keys: 'api_key', 'engine', 'language'
        
        Returns:
            bool: True if authentication successful
            
        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Validate required credentials
            required_fields = ['api_key', 'engine', 'language']
            for field in required_fields:
                if field not in credentials:
                    raise AuthenticationError(f"Missing required credential: {field}")
            
            api_key = credentials['api_key']
            if not isinstance(api_key, str) or not api_key.strip():
                raise AuthenticationError("Invalid api_key")
            
            engine = credentials['engine']
            if not isinstance(engine, str) or engine not in self.metadata['engines']:
                raise AuthenticationError(f"Invalid engine. Must be one of: {self.metadata['engines']}")
            
            language = credentials['language']
            if not isinstance(language, str) or language not in self.metadata['languages']:
                raise AuthenticationError(f"Invalid language. Must be one of: {self.metadata['languages']}")
            
            # Store credentials
            self._api_key = api_key
            self._engine = engine
            self._language = language
            
            # In a real implementation, you would initialize the appropriate OCR client
            # For this example, we'll simulate the authentication process
            
            # Simulate client initialization based on engine
            if engine == 'tesseract':
                # In real implementation: pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
                self._client = "tesseract_client_instance"
            elif engine == 'google_vision':
                # In real implementation: vision.ImageAnnotatorClient(credentials=credentials)
                self._client = "google_vision_client_instance"
            elif engine == 'aws_textract':
                # In real implementation: boto3.client('textract', aws_access_key_id=..., aws_secret_access_key=...)
                self._client = "aws_textract_client_instance"
            elif engine == 'azure_cognitive':
                # In real implementation: ComputerVisionClient(endpoint, CognitiveServicesCredentials(api_key))
                self._client = "azure_cognitive_client_instance"
            
            # Test authentication by making a simple API call
            # In real implementation: client.detect_text() or similar
            auth_test_result = {
                'success': True,
                'engine': engine,
                'language': language,
                'available': True
            }
            
            if not auth_test_result.get('success', False):
                raise AuthenticationError("OCR authentication test failed")
            
            self.status = self.status.CONNECTED
            self.update_activity()
            
            return True
            
        except Exception as e:
            self.status = self.status.ERROR
            raise AuthenticationError(f"OCR authentication failed: {str(e)}")
    
    def execute_action(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an OCR action.
        
        Args:
            action_name (str): Name of the action to execute
            params (Dict[str, Any]): Parameters for the action
        
        Returns:
            Dict[str, Any]: Result of the action execution
            
        Raises:
            ActionError: If action execution fails
            AuthenticationError: If not authenticated
        """
        if not self.is_connected():
            raise AuthenticationError("Not authenticated with OCR service")
        
        if not self.validate_params(action_name, params):
            raise ActionError(f"Invalid parameters for action '{action_name}'")
        
        try:
            self.update_activity()
            
            if action_name == "extract_text":
                return self._extract_text(params)
            elif action_name == "extract_text_with_layout":
                return self._extract_text_with_layout(params)
            elif action_name == "detect_document_structure":
                return self._detect_document_structure(params)
            elif action_name == "extract_tables":
                return self._extract_tables(params)
            else:
                raise ActionError(f"Unknown action: {action_name}")
                
        except Exception as e:
            raise ActionError(f"Failed to execute action '{action_name}': {str(e)}")
    
    def list_actions(self) -> List[Dict[str, Any]]:
        """
        List all available OCR actions.
        
        Returns:
            List[Dict[str, Any]]: List of available actions
        """
        return [
            {
                'name': 'extract_text',
                'description': 'Extract text from an image',
                'required_params': ['image'],
                'optional_params': ['confidence_threshold', 'preprocessing'],
                'example': {
                    'image': 'base64_encoded_image_data',
                    'confidence_threshold': 0.8,
                    'preprocessing': 'enhance_contrast'
                }
            },
            {
                'name': 'extract_text_with_layout',
                'description': 'Extract text with layout information (bounding boxes)',
                'required_params': ['image'],
                'optional_params': ['include_coordinates', 'group_by_blocks'],
                'example': {
                    'image': 'base64_encoded_image_data',
                    'include_coordinates': True,
                    'group_by_blocks': True
                }
            },
            {
                'name': 'detect_document_structure',
                'description': 'Detect document structure (headers, paragraphs, lists)',
                'required_params': ['image'],
                'optional_params': ['structure_types', 'confidence_threshold'],
                'example': {
                    'image': 'base64_encoded_image_data',
                    'structure_types': ['header', 'paragraph', 'list'],
                    'confidence_threshold': 0.7
                }
            },
            {
                'name': 'extract_tables',
                'description': 'Extract tabular data from images',
                'required_params': ['image'],
                'optional_params': ['table_format', 'include_headers'],
                'example': {
                    'image': 'base64_encoded_image_data',
                    'table_format': 'csv',
                    'include_headers': True
                }
            }
        ]
    
    def _extract_text(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract text from an image.
        
        Args:
            params (Dict[str, Any]): Extraction parameters
            
        Returns:
            Dict[str, Any]: Extraction result
        """
        image = params['image']
        confidence_threshold = params.get('confidence_threshold', 0.8)
        preprocessing = params.get('preprocessing', 'none')
        
        # Validate image
        if not isinstance(image, str) or not image.strip():
            raise ActionError("Image must be a non-empty string (base64 encoded)")
        
        # Validate confidence threshold
        if not isinstance(confidence_threshold, (int, float)) or confidence_threshold < 0 or confidence_threshold > 1:
            raise ActionError("confidence_threshold must be between 0 and 1")
        
        # Validate preprocessing
        valid_preprocessing = ['none', 'enhance_contrast', 'denoise', 'sharpen', 'binarize']
        if preprocessing not in valid_preprocessing:
            raise ActionError(f"preprocessing must be one of: {valid_preprocessing}")
        
        # In a real implementation, you would process the image with OCR
        # For this example, we'll simulate the text extraction
        
        # Simulate OCR processing based on engine
        if self._engine == 'tesseract':
            # In real implementation: pytesseract.image_to_string(image, lang=self._language)
            extracted_text = "This is simulated OCR text extracted using Tesseract engine. The text contains multiple lines and paragraphs that were detected in the image."
        elif self._engine == 'google_vision':
            # In real implementation: client.text_detection(image=image)
            extracted_text = "Google Vision API detected text: This is a sample document with various text elements including headers, paragraphs, and bullet points."
        elif self._engine == 'aws_textract':
            # In real implementation: client.detect_document_text(Document={'Bytes': image_bytes})
            extracted_text = "AWS Textract extracted text: Document analysis completed successfully with high confidence scores for text detection."
        else:
            extracted_text = f"Azure Cognitive Services OCR result: Text extracted using {self._engine} engine with {self._language} language support."
        
        # Simulate confidence scores
        confidence_scores = {
            'overall': 0.92,
            'word_level': [0.95, 0.89, 0.91, 0.88, 0.93],
            'line_level': [0.94, 0.90, 0.92]
        }
        
        # Filter by confidence threshold
        filtered_text = extracted_text  # In real implementation, filter based on confidence
        
        return {
            'success': True,
            'extracted_text': filtered_text,
            'confidence_scores': confidence_scores,
            'confidence_threshold': confidence_threshold,
            'preprocessing': preprocessing,
            'engine': self._engine,
            'language': self._language,
            'text_length': len(filtered_text),
            'timestamp': self.last_activity.isoformat() if self.last_activity else None
        }
    
    def _extract_text_with_layout(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract text with layout information.
        
        Args:
            params (Dict[str, Any]): Extraction parameters
            
        Returns:
            Dict[str, Any]: Extraction result with layout
        """
        image = params['image']
        include_coordinates = params.get('include_coordinates', True)
        group_by_blocks = params.get('group_by_blocks', True)
        
        # Validate image
        if not isinstance(image, str) or not image.strip():
            raise ActionError("Image must be a non-empty string (base64 encoded)")
        
        # In a real implementation, you would extract text with bounding boxes
        # For this example, we'll simulate the layout extraction
        
        # Simulate layout detection
        layout_result = {
            'blocks': [
                {
                    'text': 'Document Title',
                    'type': 'header',
                    'confidence': 0.95,
                    'bounding_box': {'x': 100, 'y': 50, 'width': 200, 'height': 30}
                },
                {
                    'text': 'This is the first paragraph of the document.',
                    'type': 'paragraph',
                    'confidence': 0.92,
                    'bounding_box': {'x': 100, 'y': 100, 'width': 400, 'height': 50}
                },
                {
                    'text': '• First bullet point\n• Second bullet point',
                    'type': 'list',
                    'confidence': 0.89,
                    'bounding_box': {'x': 100, 'y': 170, 'width': 300, 'height': 60}
                }
            ],
            'full_text': 'Document Title\nThis is the first paragraph of the document.\n• First bullet point\n• Second bullet point'
        }
        
        # Filter based on parameters
        if not include_coordinates:
            for block in layout_result['blocks']:
                block.pop('bounding_box', None)
        
        if not group_by_blocks:
            layout_result['blocks'] = [
                {'text': block['text'], 'confidence': block['confidence']}
                for block in layout_result['blocks']
            ]
        
        return {
            'success': True,
            'layout_result': layout_result,
            'include_coordinates': include_coordinates,
            'group_by_blocks': group_by_blocks,
            'engine': self._engine,
            'language': self._language,
            'timestamp': self.last_activity.isoformat() if self.last_activity else None
        }
    
    def _detect_document_structure(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect document structure.
        
        Args:
            params (Dict[str, Any]): Detection parameters
            
        Returns:
            Dict[str, Any]: Structure detection result
        """
        image = params['image']
        structure_types = params.get('structure_types', ['header', 'paragraph', 'list'])
        confidence_threshold = params.get('confidence_threshold', 0.7)
        
        # Validate image
        if not isinstance(image, str) or not image.strip():
            raise ActionError("Image must be a non-empty string (base64 encoded)")
        
        # Validate structure types
        valid_types = ['header', 'paragraph', 'list', 'table', 'footer', 'caption']
        for structure_type in structure_types:
            if structure_type not in valid_types:
                raise ActionError(f"Invalid structure type: {structure_type}")
        
        # In a real implementation, you would analyze document structure
        # For this example, we'll simulate the structure detection
        
        structure_result = {
            'detected_structures': [
                {
                    'type': 'header',
                    'text': 'Main Title',
                    'confidence': 0.95,
                    'position': {'page': 1, 'block': 1}
                },
                {
                    'type': 'paragraph',
                    'text': 'Introduction paragraph content...',
                    'confidence': 0.88,
                    'position': {'page': 1, 'block': 2}
                },
                {
                    'type': 'list',
                    'text': 'Item 1\nItem 2\nItem 3',
                    'confidence': 0.92,
                    'position': {'page': 1, 'block': 3}
                }
            ],
            'document_summary': {
                'total_blocks': 3,
                'structure_types_found': ['header', 'paragraph', 'list'],
                'average_confidence': 0.92
            }
        }
        
        # Filter by confidence threshold
        filtered_structures = [
            struct for struct in structure_result['detected_structures']
            if struct['confidence'] >= confidence_threshold
        ]
        
        structure_result['detected_structures'] = filtered_structures
        
        return {
            'success': True,
            'structure_result': structure_result,
            'structure_types': structure_types,
            'confidence_threshold': confidence_threshold,
            'engine': self._engine,
            'language': self._language,
            'timestamp': self.last_activity.isoformat() if self.last_activity else None
        }
    
    def _extract_tables(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract tabular data from images.
        
        Args:
            params (Dict[str, Any]): Extraction parameters
            
        Returns:
            Dict[str, Any]: Table extraction result
        """
        image = params['image']
        table_format = params.get('table_format', 'csv')
        include_headers = params.get('include_headers', True)
        
        # Validate image
        if not isinstance(image, str) or not image.strip():
            raise ActionError("Image must be a non-empty string (base64 encoded)")
        
        # Validate table format
        valid_formats = ['csv', 'json', 'html', 'markdown']
        if table_format not in valid_formats:
            raise ActionError(f"table_format must be one of: {valid_formats}")
        
        # In a real implementation, you would extract tables from the image
        # For this example, we'll simulate the table extraction
        
        # Simulate table detection and extraction
        table_data = [
            ['Name', 'Age', 'City', 'Occupation'],
            ['John Doe', '30', 'New York', 'Engineer'],
            ['Jane Smith', '25', 'San Francisco', 'Designer'],
            ['Bob Johnson', '35', 'Chicago', 'Manager']
        ]
        
        # Format based on requested format
        if table_format == 'csv':
            formatted_data = '\n'.join([','.join(row) for row in table_data])
        elif table_format == 'json':
            headers = table_data[0] if include_headers else None
            rows = table_data[1:] if include_headers else table_data
            formatted_data = json.dumps([
                dict(zip(headers, row)) for row in rows
            ], indent=2)
        elif table_format == 'html':
            formatted_data = '<table>\n'
            for i, row in enumerate(table_data):
                tag = 'th' if i == 0 and include_headers else 'td'
                formatted_data += f'  <tr>{"".join([f"<{tag}>{cell}</{tag}>" for cell in row])}</tr>\n'
            formatted_data += '</table>'
        else:  # markdown
            formatted_data = '| ' + ' | '.join(table_data[0]) + ' |\n'
            formatted_data += '| ' + ' | '.join(['---'] * len(table_data[0])) + ' |\n'
            for row in table_data[1:]:
                formatted_data += '| ' + ' | '.join(row) + ' |\n'
        
        table_result = {
            'tables': [
                {
                    'data': table_data,
                    'formatted_data': formatted_data,
                    'format': table_format,
                    'rows': len(table_data),
                    'columns': len(table_data[0]) if table_data else 0,
                    'confidence': 0.91
                }
            ],
            'total_tables': 1
        }
        
        return {
            'success': True,
            'table_result': table_result,
            'table_format': table_format,
            'include_headers': include_headers,
            'engine': self._engine,
            'language': self._language,
            'timestamp': self.last_activity.isoformat() if self.last_activity else None
        }
    
    def validate_params(self, action_name: str, params: Dict[str, Any]) -> bool:
        """
        Validate parameters for OCR actions.
        
        Args:
            action_name (str): Name of the action
            params (Dict[str, Any]): Parameters to validate
            
        Returns:
            bool: True if parameters are valid, False otherwise
        """
        if not super().validate_params(action_name, params):
            return False
        
        # All OCR actions require an image
        if 'image' not in params or not isinstance(params['image'], str):
            return False
        
        if action_name == "extract_text":
            # Additional validation for extract_text
            if 'confidence_threshold' in params:
                threshold = params['confidence_threshold']
                if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 1:
                    return False
        
        if action_name == "detect_document_structure":
            # Additional validation for detect_document_structure
            if 'structure_types' in params:
                if not isinstance(params['structure_types'], list):
                    return False
        
        if action_name == "extract_tables":
            # Additional validation for extract_tables
            if 'table_format' in params:
                valid_formats = ['csv', 'json', 'html', 'markdown']
                if params['table_format'] not in valid_formats:
                    return False
        
        return True
    
    def disconnect(self) -> None:
        """Disconnect from OCR service."""
        super().disconnect()
        self._client = None
        self._api_key = None
        self._engine = None
        self._language = None
