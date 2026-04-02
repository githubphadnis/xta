from app.services.statement_service import StatementService


def test_process_file_returns_contract_for_unsupported_extension() -> None:
    service = StatementService()
    result = service.process_file(b"hello", "sample.txt")
    assert "rows" in result
    assert "meta" in result
    assert result["rows"] == []
    assert result["meta"]["confidence"] == "low"
