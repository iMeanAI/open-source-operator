import os
import asyncio
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from sanic.log import logger
from transformers import AutoProcessor, AutoModelForImageTextToText, TextIteratorStreamer
import torch
from threading import Thread

class HostGenerator:
    def __init__(self, model="convergence-ai/proxy-lite-3b"):
        self.model = model
        self.pool = ThreadPoolExecutor(max_workers=os.cpu_count() * 2)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = None
        self.model_instance = None
    
    def format_messages(self, raw_messages: list) -> list:
        formatted_messages = []
        
        for msg in raw_messages:
            if isinstance(msg.get("content"), list):
                for item in msg["content"]:
                    if isinstance(item, dict):
                        if "type" in item and item["type"] in ["text", "image_url"]:
                            formatted_msg = {
                                "role": msg.get("role", "user"),
                                "content": [item]
                            }
                            formatted_messages.append(formatted_msg)
            else:
                formatted_msg = {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                }
                formatted_messages.append(formatted_msg)
        
        return formatted_messages

    async def request(self, messages: list = None, max_tokens: int = 500, temperature: float = 0.7) -> (str, str):
        loop = asyncio.get_event_loop()
        try:
            # 首先格式化消息
            # formatted_messages = self.format_messages(messages) if messages else []
            response = await loop.run_in_executor(
                self.pool, 
                partial(self.chat, messages, max_tokens, temperature)
            )
            return response, ""
        except Exception as e:
            logger.error(f"Error in ProxyLiteGenerator.request: {e}")
            return "", str(e)
    
    def chat(self, messages, max_tokens=500, temperature=0.7):
        # 如果模型尚未加载，则加载模型
        if self.processor is None or self.model_instance is None:
            try:
                self.processor = AutoProcessor.from_pretrained(self.model)
                self.model_instance = AutoModelForImageTextToText.from_pretrained(
                    self.model,
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                    device_map=self.device
                )
                logger.info(f"Model {self.model} loaded successfully on {self.device}")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                return f"Error loading model: {str(e)}"
        
        try:
            # 使用chat template处理输入
            template = self.processor.apply_chat_template(messages, add_generation_prompt=True)
            inputs = self.processor(
                text=template,
                return_tensors="pt",
                padding=True
            ).to(self.device)

            # 设置streamer来跳过提示部分
            streamer = TextIteratorStreamer(
                self.processor.tokenizer,
                skip_prompt=True,
                skip_special_tokens=True
            )

            # 设置生成参数
            generation_kwargs = dict(
                input_ids=inputs["input_ids"],
                attention_mask=inputs.get("attention_mask", None),
                streamer=streamer,
                max_new_tokens=max_tokens,
                do_sample=temperature > 0,
                temperature=temperature,
                top_p=0.95,
                repetition_penalty=1.1
            )

            # 在单独的线程中运行生成过程
            thread = Thread(target=self.model_instance.generate, kwargs=generation_kwargs)
            thread.start()

            # 收集生成的文本
            generated_text = ""
            for text in streamer:
                generated_text += text

            thread.join()
            return generated_text.strip()

        except Exception as e:
            logger.error(f"Error in chat processing: {e}")
            return f"Error processing chat: {str(e)}"