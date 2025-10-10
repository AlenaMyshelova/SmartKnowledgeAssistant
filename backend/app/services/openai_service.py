from openai import OpenAI
from typing import List, Dict, Any
from app.core.config import settings

class OpenAIService:
    """
    Сервис для работы с OpenAI API.
    Инкапсулирует всю логику взаимодействия с ChatGPT.
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def generate_chat_response(
        self, 
        user_message: str, 
        context: str = "", 
        scarcity_note: str = ""
    ) -> str:
        """
        Генерация ответа через OpenAI ChatGPT.
        
        Args:
            user_message: Сообщение пользователя
            context: Контекст из базы знаний
            scarcity_note: Заметка о недостатке данных
            
        Returns:
            Ответ от ChatGPT
        """
        try:
            # Системный промпт - инструкция для AI
            system_prompt = self._build_system_prompt()
            
            # Пользовательский промпт с контекстом
            user_prompt = self._build_user_prompt(user_message, context, scarcity_note)
            
            # Запрос к OpenAI
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"OpenAI API error: {e}")
            raise Exception(f"Failed to generate response: {str(e)}")
    
    def _build_system_prompt(self) -> str:
        """Создание системного промпта."""
        return """You are a Smart Knowledge Assistant for TechNova company. 
        Your primary task is to help users with questions about the company using the provided information.
        
        Guidelines:
        - Use the provided company information as your primary source
        - If the information is relevant and sufficient, base your answer on it
        - If there isn't enough relevant company information, you may use general knowledge but clearly mention this
        - Be helpful, professional, and concise
        - If you use specific company data, mention which sections you referenced
        - Always try to be as accurate as possible"""
    
    def _build_user_prompt(self, user_message: str, context: str, scarcity_note: str) -> str:
        """Создание пользовательского промпта с контекстом."""
        prompt_parts = []
        
        if context:
            prompt_parts.append("Relevant company information:")
            prompt_parts.append(context)
            prompt_parts.append("---")
        
        prompt_parts.append(f"User question: {user_message}")
        
        if scarcity_note:
            prompt_parts.append(scarcity_note)
        
        return "\n".join(prompt_parts)

# Создаем единственный экземпляр сервиса (Singleton pattern)
openai_service = OpenAIService()