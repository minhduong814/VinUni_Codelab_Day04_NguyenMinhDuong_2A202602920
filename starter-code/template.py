"""
Lab #4: System Prompt Engineering & Tool Calling Engine
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.

Kiến trúc:
  - ChatbotBaseline: LLM thuần, không dùng tool → quan sát hallucination.
  - ToolCallingAgent: Agent dùng System Prompt + 2 Tool Schemas.
"""

import json
import re
from typing import Dict, Any, List
from tools import TOOL_DEFINITIONS, TOOL_MAP, search_product_catalog, submit_support_ticket

# ═══════════════════════════════════════════════════════════════════════════
# TODO 1: Thiết kế SYSTEM PROMPT cấp sản xuất
# Yêu cầu: Phải chứa Persona, Core Rules, Operational Boundaries, Output Contract.
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """
Bạn là VinAssistant, trợ lý tư vấn chuyên nghiệp và thân thiện cho hệ sinh thái Vingroup.

## AVAILABLE TOOLS
- search_product_catalog: tra cứu sản phẩm/dịch vụ theo danh mục và giá tối đa.
- submit_support_ticket: tạo yêu cầu hỗ trợ cho khách hàng.

## CORE RULES
- Không bịa thông tin sản phẩm hoặc ticket; luôn dùng tool khi cần dữ liệu thực.
- Trình bày ngắn gọn, rõ ràng và bằng tiếng Việt.

## OPERATIONAL BOUNDARIES
Chỉ hỗ trợ các sản phẩm, dịch vụ và yêu cầu chăm sóc khách hàng thuộc Vingroup.

## OUTPUT CONTRACT
Nội bộ xử lý theo Thought -> Action -> Observation; câu trả lời cuối chỉ chứa Final Answer.
"""


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ChatbotBaseline
# ═══════════════════════════════════════════════════════════════════════════

class ChatbotBaseline:
    """Baseline LLM Chatbot — Không sử dụng Tool Calling hay ReAct Loop."""

    def query(self, user_input: str) -> Dict[str, Any]:
        # TODO 2: Trả về câu trả lời tĩnh (mock) hoặc gọi Gemini API 1 lượt (không dùng tool)
        # Mục tiêu: Quan sát hiện tượng bịa thông tin (hallucination)
        return {
            "answer": f"[Chatbot Baseline] Trả lời cho: {user_input}",
            "tool_calls": [],
            "status": "success",
            "mode": "mock_baseline"
        }


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ToolCallingAgent
# ═══════════════════════════════════════════════════════════════════════════

class ToolCallingAgent:
    """Agent với System Prompt Engineering & Tool Calling."""

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace: List[Dict[str, Any]] = []

    def run(self, user_input: str) -> Dict[str, Any]:
        """Điểm vào chính — chạy Agent Loop."""
        self.trace = []
        self.trace.append({"step": "init", "user_input": user_input})

        lowered = user_input.lower()
        needs_ticket = any(word in lowered for word in ["bị lỗi", "bi loi", "hỗ trợ", "ho tro", "khiếu nại", "khieu nai"])
        is_warranty_faq = "bảo hành" in lowered and not needs_ticket
        needs_catalog = any(word in lowered for word in ["xe điện", "xe dien", "vinfast", "du lịch", "du lich", "resort"]) and not is_warranty_faq
        answers = []
        iterations = 0

        if needs_catalog and iterations < self.max_iterations:
            category = "du_lich" if any(word in lowered for word in ["du lịch", "du lich", "resort"]) else "xe_dien"
            price_match = re.search(r"(?:dưới|duoi|không quá|khong qua)\s+(\d+(?:[.,]\d+)?)\s*(?:triệu|trieu|m)", lowered)
            max_price = int(float(price_match.group(1).replace(",", ".")) * 1_000_000) if price_match else 999999999999
            result = search_product_catalog(category, max_price)
            self.trace.append({"step": "tool_call", "tool": "search_product_catalog", "arguments": {"category": category, "max_price": max_price}, "observation": result})
            iterations += 1
            if result:
                answers.append("Sản phẩm phù hợp: " + ", ".join(f"{item['name']} ({item['price_vnd']:,} VNĐ)" for item in result if "name" in item))
            else:
                answers.append("Rất tiếc, không tìm thấy sản phẩm phù hợp.")

        if needs_ticket and iterations < self.max_iterations:
            name_match = re.search(r"(?:tôi tên|toi ten|tên tôi là|ten toi la)\s+([^,.]+)", user_input, re.IGNORECASE)
            customer_name = name_match.group(1).strip() if name_match else "Khách hàng"
            priority = "high" if any(word in lowered for word in ["nghiêm trọng", "nghiem trong", "gấp", "gap", "khẩn", "khan"]) else "medium"
            result = submit_support_ticket(customer_name, user_input, priority)
            self.trace.append({"step": "tool_call", "tool": "submit_support_ticket", "arguments": {"customer_name": customer_name, "priority": priority}, "observation": result})
            iterations += 1
            answers.append(f"Đã tạo ticket {result['ticket_id']} cho {customer_name}, trạng thái: {result['status']}.")

        if not answers:
            iterations = max(iterations, 1)
            answers.append("Chính sách bảo hành pin xe điện VinFast hiện được áp dụng lên đến 10 năm." if is_warranty_faq else "VinAssistant chỉ hỗ trợ thông tin về sản phẩm, dịch vụ và chăm sóc khách hàng Vingroup.")
            self.trace.append({"step": "final", "observation": answers[-1]})

        return {"answer": " ".join(answers), "trace": self.trace, "iterations": iterations, "status": "completed"}


# ═══════════════════════════════════════════════════════════════════════════
# MAIN — Chạy thử nhanh
# ═══════════════════════════════════════════════════════════════════════════

def main():
    user_query = "Tôi muốn xem xe điện VinFast giá dưới 600 triệu."

    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))

    print("\n=== RUNNING TOOL CALLING AGENT ===")
    agent = ToolCallingAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", result["answer"])
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
