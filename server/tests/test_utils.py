"""
Tests for utility functions
"""
import pytest
import datetime
from unittest.mock import Mock
from server.utils import (
    upper_case, parse_iso_timestamp, extract_timestamp_from_object_name,
    extract_composite_from_object_name, default_json_handler, initialize_composite_state
)


class TestUpperCase:
    """Test upper_case function"""
    
    def test_single_word(self):
        assert upper_case("clouds") == "Clouds"
    
    def test_multiple_words(self):
        assert upper_case("day_convection") == "Day Convection"
    
    def test_short_segments(self):
        assert upper_case("ir_clouds") == "IR Clouds"
    
    def test_mixed_case(self):
        assert upper_case("true_color") == "True Color"
    
    def test_empty_string(self):
        assert upper_case("") == ""


class TestParseIsoTimestamp:
    """Test parse_iso_timestamp function"""
    
    def test_utc_timestamp_with_z(self):
        result = parse_iso_timestamp("2025-01-15T12:00:00Z")
        expected = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        assert result == expected
    
    def test_utc_timestamp_with_offset(self):
        result = parse_iso_timestamp("2025-01-15T12:00:00+00:00")
        expected = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        assert result == expected
    
    def test_naive_timestamp(self):
        result = parse_iso_timestamp("2025-01-15T12:00:00")
        expected = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        assert result == expected
    
    def test_invalid_format(self):
        with pytest.raises(ValueError):
            parse_iso_timestamp("invalid-timestamp")


class TestExtractTimestampFromObjectName:
    """Test extract_timestamp_from_object_name function"""
    
    def test_valid_object_name(self):
        object_name = "ir_clouds/2025/01/15/himawari_ir_clouds_20250115_1200.tif"
        result = extract_timestamp_from_object_name(object_name)
        expected = datetime.datetime(2025, 1, 15, 12, 0, tzinfo=datetime.timezone.utc)
        assert result == expected
    
    def test_different_composite(self):
        object_name = "true_color/2025/01/15/himawari_true_color_20250115_0800.tif"
        result = extract_timestamp_from_object_name(object_name)
        expected = datetime.datetime(2025, 1, 15, 8, 0, tzinfo=datetime.timezone.utc)
        assert result == expected
    
    def test_invalid_object_name(self):
        object_name = "invalid/path/file.tif"
        result = extract_timestamp_from_object_name(object_name)
        assert result is None
    
    def test_wrong_extension(self):
        object_name = "ir_clouds/2025/01/15/himawari_ir_clouds_20250115_1200.jpg"
        result = extract_timestamp_from_object_name(object_name)
        assert result is None


class TestExtractCompositeFromObjectName:
    """Test extract_composite_from_object_name function"""
    
    def test_valid_composite(self):
        object_name = "ir_clouds/2025/01/15/himawari_ir_clouds_20250115_1200.tif"
        available_composites = ['ir_clouds', 'true_color', 'ash']
        result = extract_composite_from_object_name(object_name, available_composites)
        assert result == "ir_clouds"
    
    def test_different_composite(self):
        object_name = "true_color/2025/01/15/himawari_true_color_20250115_1200.tif"
        available_composites = ['ir_clouds', 'true_color', 'ash']
        result = extract_composite_from_object_name(object_name, available_composites)
        assert result == "true_color"
    
    def test_unavailable_composite(self):
        object_name = "unknown/2025/01/15/himawari_unknown_20250115_1200.tif"
        available_composites = ['ir_clouds', 'true_color', 'ash']
        result = extract_composite_from_object_name(object_name, available_composites)
        assert result is None
    
    def test_invalid_object_name(self):
        object_name = "invalid/path/file.tif"
        available_composites = ['ir_clouds', 'true_color', 'ash']
        result = extract_composite_from_object_name(object_name, available_composites)
        assert result is None


class TestDefaultJsonHandler:
    """Test default_json_handler function"""
    
    def test_datetime_serialization(self):
        dt = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        result = default_json_handler(dt)
        assert result == "2025-01-15T12:00:00+00:00"
    
    def test_unsupported_type(self):
        with pytest.raises(TypeError):
            default_json_handler(set([1, 2, 3]))


class TestInitializeCompositeState:
    """Test initialize_composite_state function"""
    
    def test_empty_bucket(self):
        mock_client = Mock()
        mock_client.list_objects.return_value = []
        
        available_composites = ['ir_clouds', 'true_color']
        result = initialize_composite_state(mock_client, available_composites)
        
        expected = {'ir_clouds': None, 'true_color': None}
        assert result == expected
    
    def test_with_objects(self):
        mock_client = Mock()
        
        # Mock objects
        mock_obj1 = Mock()
        mock_obj1.object_name = "ir_clouds/2025/01/15/himawari_ir_clouds_20250115_1200.tif"
        mock_obj2 = Mock()
        mock_obj2.object_name = "ir_clouds/2025/01/15/himawari_ir_clouds_20250115_1000.tif"
        mock_obj3 = Mock()
        mock_obj3.object_name = "true_color/2025/01/15/himawari_true_color_20250115_0800.tif"
        
        mock_client.list_objects.return_value = [mock_obj1, mock_obj2, mock_obj3]
        
        available_composites = ['ir_clouds', 'true_color']
        result = initialize_composite_state(mock_client, available_composites)
        
        # Should pick the latest timestamp for each composite
        expected_ir_clouds = datetime.datetime(2025, 1, 15, 12, 0, tzinfo=datetime.timezone.utc)
        expected_true_color = datetime.datetime(2025, 1, 15, 8, 0, tzinfo=datetime.timezone.utc)
        
        assert result['ir_clouds'] == expected_ir_clouds
        assert result['true_color'] == expected_true_color
    
    def test_unknown_composite_ignored(self):
        mock_client = Mock()
        
        # Mock object with unknown composite
        mock_obj = Mock()
        mock_obj.object_name = "unknown/2025/01/15/himawari_unknown_20250115_1200.tif"
        
        mock_client.list_objects.return_value = [mock_obj]
        
        available_composites = ['ir_clouds', 'true_color']
        result = initialize_composite_state(mock_client, available_composites)
        
        expected = {'ir_clouds': None, 'true_color': None}
        assert result == expected
