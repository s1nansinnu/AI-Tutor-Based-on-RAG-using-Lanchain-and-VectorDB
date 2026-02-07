from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.chains import create_history_aware_retriever, create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from chroma_utils import vectorstore
from config import get_settings
import json
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

retriever = vectorstore.as_retriever(search_kwargs={"k": settings.retriever_k})

# Context-aware retriever prompt 
contextualize_q_system_prompt = (
    """You are an AI tutor helping students learn. 
    Given a chat history and the latest user question which might reference context in the chat history, 
    formulate a standalone question which can be understood without the chat history. 
    Do NOT answer the question, just reformulate it if needed and otherwise return it as is."""
)

contextualize_q_prompt = ChatPromptTemplate.from_messages([
    ("system", contextualize_q_system_prompt),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

qa_system_prompt = """You are an AI TUTOR designed exclusively for educational purposes. Your ONLY role is to help students learn and understand concepts.

STRICT RULES - WHAT YOU CAN DO:
✅ Explain concepts, theories, and ideas
✅ Answer questions about academic subjects
✅ Help with homework by guiding (not doing it for them)
✅ Provide examples and analogies
✅ Break down complex topics into simple explanations
✅ Answer questions about the uploaded documents
✅ Clarify doubts and misconceptions
✅ Teach problem-solving approaches

STRICT RULES - WHAT YOU CANNOT DO:
❌ Write emails, letters, or professional correspondence
❌ Create essays, articles, or blog posts for the user
❌ Write code for the user's projects (explain concepts instead)
❌ Generate creative content (poems, stories, scripts)
❌ Produce marketing or business content
❌ Write assignments or homework directly
❌ Create any content meant to be submitted as the user's work

IF USER ASKS FOR PROHIBITED CONTENT:
Politely decline and offer to TEACH them how to do it instead.

Example responses:
- "I can't write the email for you, but I can teach you the structure of a professional email!"
- "Instead of writing your essay, let me help you understand the topic and create an outline."
- "I'm here to help you learn, not do your work. Let's break down the problem together!"

Context from documents: {context}

YOUR RESPONSE - EDUCATIONAL FOCUS:
When answering:
1. Focus on TEACHING and EXPLAINING
2. Use the Socratic method when appropriate (ask guiding questions)
3. Encourage critical thinking
4. Provide step-by-step explanations
5. Use examples from the context when available
6. Make learning engaging and clear

RESPONSE FORMAT - YOU MUST FOLLOW EXACTLY:
Return ONLY a valid JSON object with this exact structure:
{{{{
  "answer": "your educational response here",
  "emotion": "one_emotion"
}}}}

Emotion options (choose ONE):
- happy: Enthusiastic teaching moments
- explaining: Teaching, detailed explanations
- thinking: Helping analyze problems
- encouraging: Motivating learning
- neutral: Factual teaching responses

CRITICAL JSON RULES:
1. Output ONLY the JSON object - nothing else
2. NO markdown (no ```json or ``` blocks)
3. NO text before the JSON
4. NO text after the JSON
5. Ensure valid JSON (proper quotes, commas, brackets)

EXAMPLE - Prohibited request:
User: "Write me an email to my professor"
{{{{
  "answer": "I'm your AI tutor, so I can't write the email for you - but I'd love to teach you how! A professional email has: 1) Clear subject line, 2) Polite greeting, 3) Concise message, 4) Call to action, 5) Professional closing. What specifically do you want to communicate to your professor? Let's build the structure together!",
  "emotion": "encouraging"
}}}}

Remember: You are a TUTOR, not a content generator. Your goal is to help users LEARN and UNDERSTAND, not to do work for them."""

qa_prompt = ChatPromptTemplate.from_messages([
    ("system", qa_system_prompt),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}")
])

def parse_llm_response(response_text: str, retry_count: int = 0, max_retries: int = 2) -> dict:
    """
    Parse LLM response to extract answer and emotion with enhanced cleaning.
    
    Args:
        response_text: Raw response from LLM
        retry_count: Current retry attempt
        max_retries: Maximum number of retries
    
    Returns:
        Dictionary with 'answer' and 'emotion' keys
    """
    valid_emotions = ["happy", "explaining", "thinking", "encouraging", "neutral"]
    
    try:
        # Clean up response text
        response_text = response_text.strip()
        
        logger.debug(f"Raw LLM response: {response_text[:200]}...")
        
        # ✅ ENHANCED: Remove common prefixes that LLMs add
        prefixes_to_remove = [
            "Here's the answer:",
            "Here's my response:",
            "Sure, here you go:",
            "The answer is:",
            "Answer:",
            "{answer:",
            "answer:}",
            "emotion:",

        ]
        for prefix in prefixes_to_remove:
            if response_text.lower().startswith(prefix.lower()):
                response_text = response_text[len(prefix):].strip()
        
        # Remove markdown code blocks
        if response_text.startswith("```json"):
            response_text = response_text.replace("```json", "", 1).strip()
        if response_text.startswith("```"):
            response_text = response_text.replace("```", "", 1).strip()
        if response_text.endswith("```"):
            response_text = response_text[:-3].strip()
        
        # ✅ ENHANCED: Extract JSON more aggressively
        # Look for the first { and last }
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            response_text = response_text[start_idx:end_idx+1]
        
        # Parse JSON
        parsed = json.loads(response_text)
        
        # Validate required fields
        if "answer" not in parsed:
            raise ValueError("Missing 'answer' field in response")
        if "emotion" not in parsed:
            logger.warning("Missing 'emotion' field, defaulting to 'neutral'")
            parsed["emotion"] = "neutral"
        
        # ✅ ENHANCED: Clean the answer text
        answer = str(parsed["answer"]).strip()
        
        # Remove any JSON artifacts that might have leaked into the answer
        # Check if answer starts with { or ends with }
        if answer.startswith('{') or answer.endswith('}'):
            logger.warning("Answer contains JSON artifacts, attempting to clean")
            # This shouldn't happen but if it does, try to extract just the text
            answer = answer.replace('{', '').replace('}', '').strip()
        
        # Validate and normalize emotion value
        emotion = str(parsed["emotion"]).lower().strip()
        
        if emotion not in valid_emotions:
            logger.warning(f"Invalid emotion '{emotion}', defaulting to 'neutral'")
            emotion = "neutral"
        
        logger.debug(f"Parsed answer length: {len(answer)}, emotion: {emotion}")
        
        return {
            "answer": answer,
            "emotion": emotion
        }
        
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error (attempt {retry_count + 1}/{max_retries}): {e}")
        logger.warning(f"Problematic text: {response_text[:500]}")
        
        # Fallback: Use the entire response as the answer
        return {
            "answer": response_text if response_text else "I apologize, I encountered an error generating a response.",
            "emotion": "neutral"
        }
        
    except Exception as e:
        logger.error(f"Error parsing LLM response: {e}")
        return {
            "answer": response_text if response_text else "I apologize, I encountered an error generating a response.",
            "emotion": "neutral"
        }


def get_rag_chain(model: str = None):
    """
    Create RAG chain that returns both answer and emotion in a single API call.
    
    Args:
        model: The Gemini model to use (defaults to settings.default_model)
    
    Returns:
        RAG chain that produces string output (JSON with answer and emotion)
    """
    if model is None:
        model = settings.default_model
        
    try:
        # Initialize LLM with API Key and configured settings
        llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.google_api_key,
            timeout=settings.model_timeout,
            max_retries=settings.model_max_retries,
            temperature=settings.model_temperature
        )
        
        # Create history-aware retriever (reformulates questions with context)
        history_aware_retriever = create_history_aware_retriever(
            llm, 
            retriever, 
            contextualize_q_prompt
        )
        
        # Create question-answer chain
        question_answer_chain = create_stuff_documents_chain(
            llm, 
            qa_prompt
        )
        
        # Combine into full RAG chain
        rag_chain = create_retrieval_chain(
            history_aware_retriever, 
            question_answer_chain
        )
        
        logger.info(f"RAG chain initialized with model: {model}")
        return rag_chain
        
    except Exception as e:
        logger.error(f"Error creating RAG chain: {e}")
        raise