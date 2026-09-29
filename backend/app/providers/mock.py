"""Mock Provider: deterministic, persona-flavoured responses so the whole platform
(debate, voting, judging, streaming UI) runs end-to-end with zero API keys.

The Agent Runtime embeds a [MOCK-HINT] block into the prompt when the resolved
provider is the mock. Swapping in a real provider keeps the architecture unchanged.
"""
import asyncio
import json
import random
import re
from typing import AsyncIterator

from app.core.config import get_settings
from app.providers.base import ChatMessage, LLMProvider

_HINT_RE = re.compile(r"\[MOCK-HINT\]\s*(\{.*?\})\s*\[/MOCK-HINT\]", re.DOTALL)

_TEMPLATES = {
    "proposal": [
        "Nhìn nhiệm vụ «{task}», tôi đề xuất một phương án theo đúng thế mạnh của vai trò {role}: bắt đầu từ mục tiêu cốt lõi, chia nhỏ thành các bước kiểm chứng được, và giữ phạm vi tối thiểu cho bước đầu. Điểm mấu chốt tôi muốn Hội đồng chú ý: đừng tối ưu quá sớm — chọn lõi đơn giản, đo lường được, rồi mới mở rộng.",
        "Phương án của tôi cho «{task}»: xác định rõ ràng buộc cứng trước, sau đó dựng khung tổng thể quanh các ràng buộc đó. Tôi ưu tiên hướng đi thực dụng — thứ chạy được ngay hôm nay và dễ thay thế vào ngày mai — thay vì kiến trúc hoàn hảo trên giấy.",
        "Về «{task}», cách tiếp cận của tôi là đặt ra 3 giả định lớn nhất rồi tìm cách vô hiệu hoá từng giả định đó. Nếu giả định nào không sụp đổ được, nó chính là trụ cột của phương án. Đây là cách tôi đề xuất để tiến hành.",
    ],
    "challenge": [
        "@{target}, tôi phản biện trực tiếp: phương án này chưa chứng minh được vì sao nó tốt hơn các lựa chọn thay thế. «{task}» đang được giải quyết bằng giả định chứ không bằng bằng chứng — hãy chỉ ra dữ kiện nào dẫn tới kết luận đó.",
        "Chờ đã @{target} — cách này đang phức tạp hoá vấn đề. Với «{task}», mỗi lớp trừu tượng thêm vào là một lớp lỗi tiềm ẩn. Chứng minh rằng lớp đó là cần thiết, nếu không tôi sẽ không ủng hộ.",
        "@{target}, điểm yếu của lập luận nằm ở chỗ: nó đẹp trong trường hợp lý tưởng nhưng không nói gì tới thất bại. «{task}» sẽ gặp trường hợp xấu nhất ngay tuần đầu. Tôi cần nghe phương án ứng phó rủi ro trước khi cân nhắc.",
    ],
    "rebuttal": [
        "@{target}, tôi giữ quan điểm nhưng điều chỉnh: phần phản biện của bạn đúng ở bề mặt — rủi ro đó có thật. Tuy nhiên nó được kiểm soát nếu ta giới hạn phạm vi bước đầu của «{task}» và chỉ mở rộng khi có số liệu. Điểm cốt lõi của phương án vẫn đứng vững.",
        "@{target}, bạn đang tấn công phần vỏ chứ không phải phần lõi. Rủi ro bạn nêu với «{task}» là thật, nhưng nó là chi phí của mọi phương án khác nhau — khác ở chỗ phương án của tôi làm rủi ro đó đo lường được. Tôi điều chỉnh một điểm: thêm bước kiểm chứng sớm.",
        "@{target}, tôi chấp nhận một phần: khả năng kiểm chứng của bạn hợp lệ. Nhưng kết luận của bạn đi quá xa. Với «{task}», điều đúng là giữ hướng đi hiện tại và bổ sung cơ chế phát hiện sớm, không phải vứt bỏ phương án.",
    ],
    "agreement": [
        "Tôi nhất trí với @{target} ở điểm cốt lõi: hướng đi cho «{task}» là hợp lý và có kiểm chứng. Đề nghị ghi nhận vào kết luận chung, kèm điều kiện kiểm chứng sớm mà @{target} đã nêu.",
        "Đồng thuận với @{target}. Với «{task}», đây là phương án cân bằng nhất giữa rủi ro và tốc độ mà Hội đồng đã thảo luận. Tôi không có phản đối nào đáng kể.",
        "@{target} thuyết phục tôi ở phần phân tích rủi ro cho «{task}». Tôi chính thức đồng ý và sẵn sàng bảo vệ kết luận này trước Vua.",
    ],
    "observation": [
        "Góc nhìn bổ sung cho «{task}»: chúng ta đang so sánh các phương án trên cùng một mặt bằng, nhưng thiếu một tiêu chí — khả năng chuyển đổi nếu giả định lớn nhất sai. Ai chọn phương án cũng nên nêu phương án B tương ứng.",
        "Nhận xét từ vai trò {role}: điểm chung của các phương án đang được đề xuất là đều phụ thuộc vào một quyết định nền tảng. Nên làm rõ quyết định đó trước, phần còn lại của «{task}» sẽ dễ phân xử hơn.",
        "Tôi để ý một điều chưa ai nhắc về «{task}»: chi phí vận hành dài hạn. Các phương án gần như ngang nhau ở bước đầu, khác nhau ở tháng thứ sáu. Đó nên là tiêu chí phân định.",
    ],
    "ask": [
        "Trả lời nhanh từ vai trò {role} về «{task}»: câu trả lời ngắn là có — nhưng điều đáng chú ý hơn là ba điều kiện đi kèm. Nếu Vua muốn, Hội đồng có thể tranh luận sâu để kiểm chứng từng điều kiện.",
        "Về «{task}»: theo góc nhìn {role}, lựa chọn hợp lý nhất hiện tại phụ thuộc vào quy mô thực tế chứ không phải lý thuyết. Tôi khuyến nghị bắt đầu với cấu hình nhỏ nhất đáp ứng được mục tiêu, rồi nâng cấp theo số liệu.",
        "Câu hỏi «{task}» nên được trả lời bằng dữ kiện trước, ý kiến sau. Dữ kiện hiện có nghiêng về một hướng khá rõ; phần ý kiến của tôi nằm ở việc đó chưa đủ để chốt — cần một vòng kiểm chứng nữa.",
    ],
}

_VOTE_RATIONALES = [
    "Phương án của {choice} chịu phản biện tốt nhất và còn nguyên vẹn sau vòng tranh luận.",
    "{choice} đưa ra điều kiện kiểm chứng rõ ràng nhất — dễ ra quyết định dựa trên đó.",
    "Trong các lựa chọn, {choice} cân bằng rủi ro và tốc độ tốt nhất cho nhiệm vụ này.",
]

_JUDGE_REASONING = [
    "Phương án được chọn chịu ít phản biện bị hư hại lõi nhất trong suốt cuộc tranh luận.",
    "Các điều kiện kiểm chứng của phương án này cụ thể và khả thi trong ngắn hạn.",
    "Rủi ro còn lại có cơ chế phát hiện sớm; các phương án còn lại để lại lỗ hổng khó đo.",
    "Hội đồng đạt đồng thuận tương đối; bất đồng còn lại mang tính tối ưu chứ không phải hướng đi.",
]


def _extract_hint(messages: list[ChatMessage]) -> dict:
    for msg in reversed(messages):
        if msg.role != "user":
            continue
        m = _HINT_RE.search(msg.content)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
    return {}


class MockProvider(LLMProvider):
    name = "mock"
    live = True

    def __init__(self, model: str = "mock-1", fallback_from: str | None = None) -> None:
        self.model = model
        self.fallback_from = fallback_from  # provider name we are standing in for
        self._rng = random.Random()

    def _task_snippet(self, hint: dict) -> str:
        task = (hint.get("task") or "nhiệm vụ của Hội đồng").strip()
        return task if len(task) <= 120 else task[:117] + "…"

    def _compose(self, messages: list[ChatMessage]) -> str:
        hint = _extract_hint(messages)
        kind = hint.get("kind", "ask")
        agent = hint.get("agent", "Agent")
        role = hint.get("role", "advisor")
        target = hint.get("target", "")
        task = self._task_snippet(hint)

        if kind == "vote":
            candidates = [c for c in (hint.get("candidates") or []) if c and c != agent] or ["Kimi"]
            choice = candidates[self._rng.randrange(len(candidates))]
            rationale = self._rng.choice(_VOTE_RATIONALES).format(choice=choice)
            return f"VOTE: {choice}\nRATIONALE: {rationale}"

        if kind == "judge":
            candidates = hint.get("candidates") or []
            winner = candidates[self._rng.randrange(len(candidates))] if candidates else "phương án đồng thuận"
            decision = f"Áp dụng hướng đi đề xuất bởi {winner} cho nhiệm vụ «{task}», với điều kiện kiểm chứng sớm trong vòng một tuần."
            return json.dumps(
                {
                    "decision": decision,
                    "reasoning": self._rng.sample(_JUDGE_REASONING, k=3),
                    "confidence": round(self._rng.uniform(0.72, 0.93), 2),
                    "open_questions": ["Ngân sách và thời hạn cụ thể của Vua cho bước kiểm chứng là gì?"],
                    "dissenting_views": [],
                },
                ensure_ascii=False,
            )

        pool = _TEMPLATES.get(kind) or _TEMPLATES["ask"]
        text = self._rng.choice(pool).format(task=task, role=role, target=target or "Hội đồng")
        return text

    async def stream(
        self, messages: list[ChatMessage], *, temperature: float = 0.7, max_tokens: int = 1024
    ) -> AsyncIterator[str]:
        settings = get_settings()
        if settings.mock_think_delay > 0:
            await asyncio.sleep(settings.mock_think_delay)
        text = self._compose(messages)
        for word in text.split(" "):
            yield word + " "
            if settings.mock_token_delay > 0:
                await asyncio.sleep(settings.mock_token_delay)

    async def generate(
        self, messages: list[ChatMessage], *, temperature: float = 0.7, max_tokens: int = 1024
    ) -> str:
        return self._compose(messages)
