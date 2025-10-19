"""
LLM Summarizer connector for Enterprise AI Agent Framework.

Provides LLM integration for text summarization and analysis.
Supports multiple LLM providers and basic error handling.
"""

import json
from typing import Dict, Any, List, Optional, Union
from .base import BaseConnector, AuthenticationError, ActionError


class LLMConnector(BaseConnector):
    """
    LLM connector for text summarization and analysis.
    
    Supports multiple LLM providers and provides actions for
    text summarization, analysis, and generation.
    """
    
    CONNECTOR_NAME = "llm"
    VERSION = "1.0.0"
    DESCRIPTION = "LLM connector for text summarization and analysis"
    
    def __init__(self, tenant_id: Optional[str] = None, **kwargs):
        """
        Initialize the LLM connector.
        
        Args:
            tenant_id (Optional[str]): Tenant identifier
            **kwargs: Additional configuration
        """
        super().__init__(
            name=self.CONNECTOR_NAME,
            version=self.VERSION,
            tenant_id=tenant_id,
            metadata={
                'service': 'llm',
                'providers': ['openai', 'anthropic', 'cohere', 'huggingface'],
                'models': ['gpt-3.5-turbo', 'gpt-4', 'claude-3', 'command']
            }
        )
        self._client = None
        self._api_key = None
        self._provider = None
        self._model = None
    
    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with LLM provider.
        
        Args:
            credentials (Dict[str, Any]): Authentication credentials
                Expected keys: 'api_key', 'provider', 'model'
        
        Returns:
            bool: True if authentication successful
            
        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Validate required credentials
            required_fields = ['api_key', 'provider', 'model']
            for field in required_fields:
                if field not in credentials:
                    raise AuthenticationError(f"Missing required credential: {field}")
            
            api_key = credentials['api_key']
            if not isinstance(api_key, str) or not api_key.strip():
                raise AuthenticationError("Invalid api_key")
            
            provider = credentials['provider']
            if not isinstance(provider, str) or provider not in self.metadata['providers']:
                raise AuthenticationError(f"Invalid provider. Must be one of: {self.metadata['providers']}")
            
            model = credentials['model']
            if not isinstance(model, str) or not model.strip():
                raise AuthenticationError("Invalid model")
            
            # Store credentials
            self._api_key = api_key
            self._provider = provider
            self._model = model
            
            # In a real implementation, you would initialize the appropriate LLM client
            # For this example, we'll simulate the authentication process
            
            # Simulate client initialization based on provider
            if provider == 'openai':
                # In real implementation: openai.OpenAI(api_key=api_key)
                self._client = "openai_client_instance"
            elif provider == 'anthropic':
                # In real implementation: anthropic.Anthropic(api_key=api_key)
                self._client = "anthropic_client_instance"
            elif provider == 'cohere':
                # In real implementation: cohere.Client(api_key=api_key)
                self._client = "cohere_client_instance"
            elif provider == 'huggingface':
                # In real implementation: HuggingFaceHub(api_key=api_key)
                self._client = "huggingface_client_instance"
            
            # Test authentication by making a simple API call
            # In real implementation: client.models.list() or similar
            auth_test_result = {
                'success': True,
                'provider': provider,
                'model': model,
                'available': True
            }
            
            if not auth_test_result.get('success', False):
                raise AuthenticationError("LLM authentication test failed")
            
            self.status = self.status.CONNECTED
            self.update_activity()
            
            return True
            
        except Exception as e:
            self.status = self.status.ERROR
            raise AuthenticationError(f"LLM authentication failed: {str(e)}")
    
    def execute_action(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an LLM action.
        
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
            raise AuthenticationError("Not authenticated with LLM provider")
        
        if not self.validate_params(action_name, params):
            raise ActionError(f"Invalid parameters for action '{action_name}'")
        
        try:
            self.update_activity()
            
            if action_name == "summarize":
                return self._summarize_text(params)
            elif action_name == "analyze":
                return self._analyze_text(params)
            elif action_name == "generate":
                return self._generate_text(params)
            elif action_name == "extract_keywords":
                return self._extract_keywords(params)
            else:
                raise ActionError(f"Unknown action: {action_name}")
                
        except Exception as e:
            raise ActionError(f"Failed to execute action '{action_name}': {str(e)}")
    
    def list_actions(self) -> List[Dict[str, Any]]:
        """
        List all available LLM actions.
        
        Returns:
            List[Dict[str, Any]]: List of available actions
        """
        return [
            {
                'name': 'summarize',
                'description': 'Summarize text content',
                'required_params': ['text'],
                'optional_params': ['max_length', 'style', 'focus'],
                'example': {
                    'text': 'Long article content here...',
                    'max_length': 200,
                    'style': 'bullet_points',
                    'focus': 'main_points'
                }
            },
            {
                'name': 'analyze',
                'description': 'Analyze text for sentiment, topics, or other insights',
                'required_params': ['text', 'analysis_type'],
                'optional_params': ['detailed', 'language'],
                'example': {
                    'text': 'Customer feedback text...',
                    'analysis_type': 'sentiment',
                    'detailed': True,
                    'language': 'en'
                }
            },
            {
                'name': 'generate',
                'description': 'Generate new text content',
                'required_params': ['prompt'],
                'optional_params': ['max_tokens', 'temperature', 'style'],
                'example': {
                    'prompt': 'Write a professional email about...',
                    'max_tokens': 500,
                    'temperature': 0.7,
                    'style': 'professional'
                }
            },
            {
                'name': 'extract_keywords',
                'description': 'Extract keywords and key phrases from text',
                'required_params': ['text'],
                'optional_params': ['max_keywords', 'min_length', 'language'],
                'example': {
                    'text': 'Article content...',
                    'max_keywords': 10,
                    'min_length': 3,
                    'language': 'en'
                }
            }
        ]
    
    def _summarize_text(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Summarize text content.
        
        Args:
            params (Dict[str, Any]): Summarization parameters
            
        Returns:
            Dict[str, Any]: Summarization result
        """
        text = params['text']
        max_length = params.get('max_length', 200)
        style = params.get('style', 'paragraph')
        focus = params.get('focus', 'main_points')
        
        # Validate text
        if not isinstance(text, str) or not text.strip():
            raise ActionError("Text must be a non-empty string")
        
        if len(text) < 50:
            raise ActionError("Text must be at least 50 characters for summarization")
        
        # Validate parameters
        if not isinstance(max_length, int) or max_length < 50 or max_length > 2000:
            raise ActionError("max_length must be between 50 and 2000")
        
        valid_styles = ['paragraph', 'bullet_points', 'numbered_list', 'brief']
        if style not in valid_styles:
            raise ActionError(f"style must be one of: {valid_styles}")
        
        # In a real implementation, you would call the LLM API
        # For this example, we'll simulate the summarization
        
        # Simulate API call based on provider
        if self._provider == 'openai':
            # In real implementation: client.chat.completions.create(...)
            summary = f"This is a simulated summary of the provided text. The main points include: [1] Key concept A, [2] Important detail B, [3] Critical insight C. The text appears to focus on {focus} and has been summarized in {style} format."
        elif self._provider == 'anthropic':
            # In real implementation: client.messages.create(...)
            summary = f"Based on the provided text, here are the key insights: • Primary theme: {focus} • Main arguments presented • Supporting evidence • Conclusion. Summary length: approximately {max_length} characters."
        else:
            summary = f"Summary: The text discusses {focus} and contains several important points relevant to the topic. This summary captures the essential information in {style} format."
        
        # Truncate to max_length if needed
        if len(summary) > max_length:
            summary = summary[:max_length-3] + "..."
        
        return {
            'success': True,
            'summary': summary,
            'original_length': len(text),
            'summary_length': len(summary),
            'style': style,
            'focus': focus,
            'provider': self._provider,
            'model': self._model,
            'timestamp': self.last_activity.isoformat() if self.last_activity else None
        }
    
    def _analyze_text(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze text for insights.
        
        Args:
            params (Dict[str, Any]): Analysis parameters
            
        Returns:
            Dict[str, Any]: Analysis result
        """
        text = params['text']
        analysis_type = params['analysis_type']
        detailed = params.get('detailed', False)
        language = params.get('language', 'en')
        
        # Validate text
        if not isinstance(text, str) or not text.strip():
            raise ActionError("Text must be a non-empty string")
        
        # Validate analysis type
        valid_types = ['sentiment', 'topics', 'entities', 'emotions', 'intent', 'language']
        if analysis_type not in valid_types:
            raise ActionError(f"analysis_type must be one of: {valid_types}")
        
        # In a real implementation, you would call the LLM API for analysis
        # For this example, we'll simulate the analysis
        
        if analysis_type == 'sentiment':
            analysis_result = {
                'sentiment': 'positive',
                'confidence': 0.85,
                'scores': {'positive': 0.7, 'neutral': 0.2, 'negative': 0.1}
            }
        elif analysis_type == 'topics':
            analysis_result = {
                'topics': ['technology', 'artificial intelligence', 'business'],
                'confidence_scores': [0.9, 0.8, 0.7],
                'topic_distribution': {'technology': 0.4, 'ai': 0.35, 'business': 0.25}
            }
        elif analysis_type == 'entities':
            analysis_result = {
                'entities': [
                    {'text': 'OpenAI', 'type': 'ORGANIZATION', 'confidence': 0.95},
                    {'text': 'GPT-4', 'type': 'PRODUCT', 'confidence': 0.9}
                ],
                'entity_count': 2
            }
        else:
            analysis_result = {
                'analysis_type': analysis_type,
                'result': f"Analysis completed for {analysis_type}",
                'confidence': 0.8
            }
        
        if detailed:
            analysis_result['detailed_analysis'] = {
                'text_length': len(text),
                'language_detected': language,
                'processing_time': '0.5s',
                'model_used': self._model
            }
        
        return {
            'success': True,
            'analysis_type': analysis_type,
            'result': analysis_result,
            'detailed': detailed,
            'provider': self._provider,
            'model': self._model,
            'timestamp': self.last_activity.isoformat() if self.last_activity else None
        }
    
    def _generate_text(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate new text content.
        
        Args:
            params (Dict[str, Any]): Generation parameters
            
        Returns:
            Dict[str, Any]: Generation result
        """
        prompt = params['prompt']
        max_tokens = params.get('max_tokens', 500)
        temperature = params.get('temperature', 0.7)
        style = params.get('style', 'natural')
        
        # Validate prompt
        if not isinstance(prompt, str) or not prompt.strip():
            raise ActionError("Prompt must be a non-empty string")
        
        # Validate parameters
        if not isinstance(max_tokens, int) or max_tokens < 10 or max_tokens > 4000:
            raise ActionError("max_tokens must be between 10 and 4000")
        
        if not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 2:
            raise ActionError("temperature must be between 0 and 2")
        
        # In a real implementation, you would call the LLM API for generation
        # For this example, we'll simulate the text generation
        
        # Simulate API call
        generated_text = f"This is a simulated response to the prompt: '{prompt[:50]}...'. The generated content follows a {style} style and is approximately {max_tokens} tokens long. The response is generated using {self._provider} with temperature {temperature}."
        
        # Truncate to approximate max_tokens (rough estimation)
        estimated_tokens = len(generated_text.split())
        if estimated_tokens > max_tokens:
            words = generated_text.split()[:max_tokens]
            generated_text = ' '.join(words)
        
        return {
            'success': True,
            'generated_text': generated_text,
            'prompt': prompt,
            'max_tokens': max_tokens,
            'temperature': temperature,
            'style': style,
            'estimated_tokens': len(generated_text.split()),
            'provider': self._provider,
            'model': self._model,
            'timestamp': self.last_activity.isoformat() if self.last_activity else None
        }
    
    def _extract_keywords(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract keywords from text.
        
        Args:
            params (Dict[str, Any]): Extraction parameters
            
        Returns:
            Dict[str, Any]: Extraction result
        """
        text = params['text']
        max_keywords = params.get('max_keywords', 10)
        min_length = params.get('min_length', 3)
        language = params.get('language', 'en')
        
        # Validate text
        if not isinstance(text, str) or not text.strip():
            raise ActionError("Text must be a non-empty string")
        
        # Validate parameters
        if not isinstance(max_keywords, int) or max_keywords < 1 or max_keywords > 50:
            raise ActionError("max_keywords must be between 1 and 50")
        
        if not isinstance(min_length, int) or min_length < 1 or min_length > 20:
            raise ActionError("min_length must be between 1 and 20")
        
        # In a real implementation, you would use NLP libraries or LLM API
        # For this example, we'll simulate keyword extraction
        
        # Simple keyword extraction simulation
        words = text.lower().split()
        word_freq = {}
        
        for word in words:
            # Remove punctuation and check length
            clean_word = ''.join(c for c in word if c.isalnum())
            if len(clean_word) >= min_length:
                word_freq[clean_word] = word_freq.get(clean_word, 0) + 1
        
        # Sort by frequency and get top keywords
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        keywords = [word for word, freq in sorted_words[:max_keywords]]
        
        # Simulate confidence scores
        keyword_scores = {word: min(1.0, freq / len(words)) for word, freq in sorted_words[:max_keywords]}
        
        return {
            'success': True,
            'keywords': keywords,
            'keyword_scores': keyword_scores,
            'total_keywords_found': len(keywords),
            'max_keywords': max_keywords,
            'min_length': min_length,
            'language': language,
            'provider': self._provider,
            'model': self._model,
            'timestamp': self.last_activity.isoformat() if self.last_activity else None
        }
    
    def validate_params(self, action_name: str, params: Dict[str, Any]) -> bool:
        """
        Validate parameters for LLM actions.
        
        Args:
            action_name (str): Name of the action
            params (Dict[str, Any]): Parameters to validate
            
        Returns:
            bool: True if parameters are valid, False otherwise
        """
        if not super().validate_params(action_name, params):
            return False
        
        if action_name in ["summarize", "extract_keywords"]:
            # Validate text
            if 'text' not in params or not isinstance(params['text'], str):
                return False
        
        if action_name == "analyze":
            # Validate text and analysis_type
            if 'text' not in params or not isinstance(params['text'], str):
                return False
            if 'analysis_type' not in params or not isinstance(params['analysis_type'], str):
                return False
        
        if action_name == "generate":
            # Validate prompt
            if 'prompt' not in params or not isinstance(params['prompt'], str):
                return False
        
        return True
    
    def disconnect(self) -> None:
        """Disconnect from LLM provider."""
        super().disconnect()
        self._client = None
        self._api_key = None
        self._provider = None
        self._model = None
