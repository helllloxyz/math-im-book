from math_im_book.services.prompt_compiler import AnswerPromptCompiler


def test_answer_prompt_compiler_includes_user_profile_summary() -> None:
    compiler = AnswerPromptCompiler()

    prompt = compiler.compile(
        question="What is a linear map?",
        summary="A linear map preserves addition and scalar multiplication.",
        detail="Detailed answer.",
        symbols={"T": "linear map from V to W"},
        symbol_conflicts=[],
        strategy_instructions="# Top Down\n\nStart broad, then narrow to details.",
        answer_style_instructions="# Default\n\nUse clear math explanations.",
        user_profile_summary="The user prefers broad overviews before details.",
    )

    assert "The user prefers broad overviews before details." in prompt
    assert "## User Profile" in prompt
