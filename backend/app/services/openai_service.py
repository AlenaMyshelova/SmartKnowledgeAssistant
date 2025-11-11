from typing import List, Dict, Any, Optional
import logging
from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

class OpenAIService:
    """
    Modern OpenAI service with chat history support and structured prompts.
    Combines the best of both legacy and new approaches.
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def generate_response(
        self,
        query: str,
        context: Optional[str] = None,
        scarcity_note: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        model: str = "gpt-3.5-turbo",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        use_structured_prompts: bool = True
    ) -> Optional[str]:
        """
        Generate AI response with context and chat history.
        
        Args:
            query: User's question/message
            context: Relevant context from knowledge base
            scarcity_note: Note about limited context
            chat_history: Previous messages in format [{"role": "user/assistant", "content": "..."}]
            model: OpenAI model to use
            max_tokens: Maximum response length
            temperature: Response creativity (0.0-1.0)
            use_structured_prompts: Whether to use structured system/user prompts (recommended)
        """
        try:
            # Build messages array
            messages = []
            
            if use_structured_prompts:
                # NEW METHOD: Use structured prompts (recommended)
                system_prompt = self._build_system_prompt()
                user_prompt = self._build_user_prompt(query, context or "", scarcity_note or "")
                
                messages.append({"role": "system", "content": system_prompt})
                
                # Add chat history if provided
                if chat_history:
                    messages.extend(chat_history)
                
                # Add structured user prompt
                messages.append({"role": "user", "content": user_prompt})
                
            else:
                # LEGACY METHOD: Simple context injection
                system_content = "You are a helpful AI assistant."
                if context:
                    system_content += f"\n\nRelevant context:\n{context}"
                if scarcity_note:
                    system_content += f"\n\nNote: {scarcity_note}"
                
                messages.append({"role": "system", "content": system_content})
                
                # Add chat history
                if chat_history:
                    messages.extend(chat_history)
                
                # Add simple query
                messages.append({"role": "user", "content": query})
            
            # Generate response
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            assistant_response = response.choices[0].message.content
            
            logger.info(
                f"Generated response: {len(assistant_response)} chars, "
                f"{response.usage.total_tokens} tokens used, "
                f"model: {model}"
            )
            
            return assistant_response
            
        except Exception as e:
            logger.error(f"Error generating OpenAI response: {e}")
            return None
    
    def _build_system_prompt(self) -> str:
        """
        Build comprehensive system prompt for TechNova Smart Knowledge Assistant.
        This defines the AI's role, behavior, and guidelines.
        """
        return """You are a Smart Knowledge Assistant for TechNova company. 
Your primary task is to help users with questions about the company using the provided information.

Guidelines:
- Use the provided company information as your primary source
- If the information is relevant and sufficient, base your answer on it
- If there isn't enough relevant company information, you may use general knowledge but clearly mention this
- Be helpful, professional, and concise
- If you use specific company data, mention which sections you referenced
- Always try to be as accurate as possible
- Maintain conversation context when responding to follow-up questions
- If asked about sensitive information not in the knowledge base, politely decline

Response Style:
- Professional but friendly tone
- Clear and structured answers
- Use bullet points or numbered lists when appropriate
- Provide actionable information when possible
- Always end with an offer to help further"""
    
    def _build_user_prompt(self, query: str, context: str, scarcity_note: str) -> str:
        """
        Build structured user prompt with context and query.
        This organizes the information for optimal AI processing.
        """
        prompt_parts = []
        
        # Add context if available
        if context:
            prompt_parts.append("=== RELEVANT COMPANY INFORMATION ===")
            prompt_parts.append(context)
            prompt_parts.append("=" * 50)
            prompt_parts.append("")
        
        # Add the user's question
        prompt_parts.append(f"USER QUESTION: {query}")
        
        # Add scarcity note if present
        if scarcity_note:
            prompt_parts.append("")
            prompt_parts.append(f"NOTE: {scarcity_note}")
        
        # Add instructions
        prompt_parts.append("")
        prompt_parts.append("Please provide a helpful and accurate response based on the information above.")
        
        return "\n".join(prompt_parts)
    
    # ===========================================
    # SPECIALIZED METHODS FOR DIFFERENT USE CASES
    # ===========================================
    
    async def generate_chat_response(
        self,
        chat_id: int,
        query: str,
        context: Optional[str] = None,
        recent_messages: Optional[List[Dict[str, str]]] = None
    ) -> Optional[str]:
        """
        Generate response specifically for chat conversations.
        Automatically includes recent chat history for context.
        """
        try:
            # Limit chat history to avoid token overflow
            limited_history = recent_messages[-5:] if recent_messages else None
            
            return await self.generate_response(
                query=query,
                context=context,
                chat_history=limited_history,
                use_structured_prompts=True
            )
        except Exception as e:
            logger.error(f"Error generating chat response for chat {chat_id}: {e}")
            return None
        
    async def get_chat_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        model: str = "gpt-3.5-turbo"
    ) -> Dict[str, Any]:
        """
        Compatibility method for chat.py
        Returns response in format: {content, tokens_used, model}
        """
        try:
            if not messages:
                return {
                    "content": "No messages to process",
                    "tokens_used": 0,
                    "model": model
                }
            
            # Extract user message and chat history
            user_message = ""
            chat_history = []
            
            # Find the last user message
            for i in range(len(messages) - 1, -1, -1):
                msg = messages[i]
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    chat_history = messages[:i]
                    break
            
            # If no user message found, take the last message
            if not user_message and messages:
                user_message = messages[-1].get("content", "")
                chat_history = messages[:-1]
            
            # Get response using existing method
            response_text = await self.generate_response(
                query=user_message,
                chat_history=chat_history,
                temperature=temperature,
                model=model,
                use_structured_prompts=True
            )
            
            # Calculate total tokens
            total_tokens = sum(self.count_tokens(msg.get("content", "")) for msg in messages)
            if response_text:
                total_tokens += self.count_tokens(response_text)
            
            return {
                "content": response_text or "Sorry, could not generate response",
                "tokens_used": total_tokens,
                "model": model
            }
            
        except Exception as e:
            logger.error(f"Error in get_chat_response: {e}")
            return {
                "content": "Error processing request",
                "tokens_used": 0,
                "model": model
            }    
    
    async def generate_summary(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """
        Generate a summary of a chat conversation.
        Useful for creating chat titles or conversation summaries.
        """
        try:
            # Build conversation text
            conversation_text = "\n".join([
                f"{msg.get('role', 'unknown').title()}: {msg.get('content', '')}"
                for msg in messages[-10:]  # Last 10 messages
            ])
            
            summary_prompt = f"""Please create a brief, descriptive title for this conversation (3-6 words max):

{conversation_text}

Title should capture the main topic discussed."""
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": summary_prompt}],
                max_tokens=50,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip().strip('"')
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return None
    
    async def extract_intent(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Extract user intent and key information from query.
        Useful for routing and analytics.
        """
        try:
            intent_prompt = f"""Analyze this user query and extract:
1. Main intent/category (question, request, complaint, compliment, etc.)
2. Key topics mentioned
3. Urgency level (low, medium, high)
4. Sentiment (positive, neutral, negative)

Query: "{query}"

Respond in JSON format:
{{"intent": "...", "topics": ["..."], "urgency": "...", "sentiment": "..."}}"""
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": intent_prompt}],
                max_tokens=150,
                temperature=0.1
            )
            
            import json
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Error extracting intent: {e}")
            return None
    
    # ===========================================
    # UTILITY METHODS
    # ===========================================
    
    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Useful for managing context length.
        """
        # Rough estimation: 1 token ≈ 4 characters for English text
        return len(text) // 4
    
    def truncate_context(self, context: str, max_tokens: int = 3000) -> str:
        """
        Truncate context to fit within token limits.
        """
        estimated_tokens = self.count_tokens(context)
        
        if estimated_tokens <= max_tokens:
            return context
        
        # Truncate to approximately max_tokens
        max_chars = max_tokens * 4
        truncated = context[:max_chars]
        
        # Try to end at a sentence boundary
        last_period = truncated.rfind('.')
        if last_period > max_chars * 0.8:  # If we can keep 80%+ of content
            truncated = truncated[:last_period + 1]
        
        return truncated + "\n\n[Content truncated for length...]"

# Create service instance
openai_service = OpenAIService()