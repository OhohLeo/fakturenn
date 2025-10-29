"""Tests for path template rendering system."""

import pytest

from app.core.path_template import (
    render_path_template,
    validate_path_template,
    get_quarter,
    get_template_examples,
)


class TestGetQuarter:
    """Test quarter calculation."""

    def test_q1_months(self):
        """Test Q1 calculation for January-March."""
        assert get_quarter("01") == "Q1"
        assert get_quarter("02") == "Q1"
        assert get_quarter("03") == "Q1"

    def test_q2_months(self):
        """Test Q2 calculation for April-June."""
        assert get_quarter("04") == "Q2"
        assert get_quarter("05") == "Q2"
        assert get_quarter("06") == "Q2"

    def test_q3_months(self):
        """Test Q3 calculation for July-September."""
        assert get_quarter("07") == "Q3"
        assert get_quarter("08") == "Q3"
        assert get_quarter("09") == "Q3"

    def test_q4_months(self):
        """Test Q4 calculation for October-December."""
        assert get_quarter("10") == "Q4"
        assert get_quarter("11") == "Q4"
        assert get_quarter("12") == "Q4"


class TestRenderPathTemplate:
    """Test path template rendering."""

    def test_simple_template(self):
        """Test simple path template with year and month."""
        context = {
            "date": "2025-10-29",
            "invoice_id": "INV-001",
            "source": "Free",
        }
        result = render_path_template("{year}/{month}/{filename}", context)
        assert result == "2025/10/{filename}"

    def test_template_with_filename(self):
        """Test template with filename variable."""
        context = {
            "date": "2025-10-29",
            "invoice_id": "INV-001",
            "source": "Free",
            "filename": "facture.pdf",
        }
        result = render_path_template("{year}/{month}/{filename}", context)
        assert result == "2025/10/facture.pdf"

    def test_template_with_month_name(self):
        """Test template with French month name."""
        context = {
            "date": "2025-10-29",
            "invoice_id": "INV-001",
            "source": "Free",
        }
        result = render_path_template("{year}/{month_name}/facture.pdf", context)
        assert result == "2025/Octobre/facture.pdf"

    def test_template_with_quarter(self):
        """Test template with quarter."""
        context = {
            "date": "2025-07-15",
            "invoice_id": "INV-001",
        }
        result = render_path_template("{year}/Q{quarter}/facture.pdf", context)
        assert result == "2025/Q3/facture.pdf"

    def test_template_with_source_and_invoice_id(self):
        """Test template with source and invoice ID."""
        context = {
            "date": "2025-10-29",
            "invoice_id": "INV-001",
            "source": "Free",
        }
        result = render_path_template(
            "{year}/{month}/{source}_{invoice_id}.pdf", context
        )
        assert result == "2025/10/Free_INV-001.pdf"

    def test_template_with_amount(self):
        """Test template with amount formatting."""
        context = {
            "date": "2025-10-29",
            "amount_eur": 99.5,
        }
        result = render_path_template("{amount}.pdf", context)
        assert result == "99.50.pdf"

    def test_missing_variable_raises_error(self):
        """Test that missing variables raise ValueError."""
        context = {
            "date": "2025-10-29",
        }
        with pytest.raises(ValueError, match="Missing template variable"):
            render_path_template("{missing_var}/facture.pdf", context)

    def test_empty_template_raises_error(self):
        """Test that empty template raises ValueError."""
        with pytest.raises(ValueError, match="Template cannot be empty"):
            render_path_template("", {})

    def test_date_parsing_short_format(self):
        """Test date parsing with short format."""
        context = {
            "date": "2025-01",  # Short format
        }
        result = render_path_template("{year}/{month}", context)
        assert result == "2025/01"


class TestValidatePathTemplate:
    """Test path template validation."""

    def test_valid_simple_template(self):
        """Test validation of valid simple template."""
        is_valid, error = validate_path_template("{year}/{month}/{filename}")
        assert is_valid
        assert error == ""

    def test_valid_complex_template(self):
        """Test validation of valid complex template."""
        is_valid, error = validate_path_template(
            "{year}/{month_name}/{source}_{invoice_id}.pdf",
        )
        assert is_valid
        assert error == ""

    def test_invalid_variable_name(self):
        """Test validation fails for unknown variable."""
        is_valid, error = validate_path_template("{year}/{invalid_var}/facture.pdf")
        assert not is_valid
        assert "Unknown variable: invalid_var" in error

    def test_empty_template_invalid(self):
        """Test validation fails for empty template."""
        is_valid, error = validate_path_template("")
        assert not is_valid
        assert "Template cannot be empty" in error

    def test_no_variables_invalid(self):
        """Test validation fails for template with no variables."""
        is_valid, error = validate_path_template("facture.pdf")
        assert not is_valid
        assert "must contain at least one variable" in error

    def test_all_valid_variables(self):
        """Test validation with all supported variables."""
        template = "{year}/{month}/{month_name}/{quarter}/{date}/{invoice_id}/{source}/{amount}/{filename}"
        is_valid, error = validate_path_template(template)
        assert is_valid
        assert error == ""


class TestGetTemplateExamples:
    """Test template examples."""

    def test_examples_exist(self):
        """Test that template examples are returned."""
        examples = get_template_examples()
        assert len(examples) > 0
        assert "By Year" in examples
        assert "By Year and Month" in examples

    def test_examples_are_valid(self):
        """Test that all examples pass validation."""
        examples = get_template_examples()
        for name, template in examples.items():
            is_valid, error = validate_path_template(template)
            assert is_valid, f"Example '{name}' is invalid: {error}"
