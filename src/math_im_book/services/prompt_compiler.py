from __future__ import annotations


BASE_ANSWER_CONTRACT = "\n".join(
    [
        "You are a careful math assistant.",
        "Answer math questions clearly and directly using the provided context.",
        "Answer in the user's language unless they request otherwise.",
        "Reuse the provided knowledge before extending it.",
        "Name knowledge gaps explicitly when the context is insufficient.",
        "Preserve symbol meanings from the Symbols block.",
        "Do not invent citations; only refer to knowledge that appears in the context.",
    ]
)


class AnswerPromptCompiler:
    def compile(
        self,
        *,
        question: str,
        summary: str,
        detail: str,
        symbols: dict[str, str],
        symbol_conflicts: list[str],
        strategy_instructions: str,
        user_profile_summary: str | None = None,
        answer_style_instructions: str | None = None,
    ) -> str:
        parts = [
            BASE_ANSWER_CONTRACT,
            strategy_instructions.strip(),
            self._user_profile_block(user_profile_summary),
            self._context_block(
                summary=summary,
                detail=detail,
                symbols=symbols,
                symbol_conflicts=symbol_conflicts,
            ),
            self._question_block(question),
        ]
        if answer_style_instructions:
            parts.append(answer_style_instructions.strip())
        return "\n\n".join(part for part in parts if part)

    @staticmethod
    def _user_profile_block(user_profile_summary: str | None) -> str:
        if not user_profile_summary:
            return ""
        summary = user_profile_summary.strip()
        if not summary:
            return ""
        return "\n".join(
            [
                "## User Profile",
                summary,
            ]
        )

    @staticmethod
    def _context_block(
        *,
        summary: str,
        detail: str,
        symbols: dict[str, str],
        symbol_conflicts: list[str],
    ) -> str:
        symbol_text = ", ".join(
            f"{name}={meaning}" for name, meaning in sorted(symbols.items())
        )
        return "\n".join(
            [
                "## Context",
                f"Summary: {summary}",
                f"Detail: {detail}",
                f"Symbols: {symbol_text or 'none'}",
                (
                    "Symbol conflicts: "
                    + (" | ".join(symbol_conflicts) if symbol_conflicts else "none")
                ),
            ]
        )

    @staticmethod
    def _question_block(question: str) -> str:
        return "\n".join(
            [
                "## Question",
                question,
            ]
        )
