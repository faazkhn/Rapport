import validate_data


def test_all_data_files_valid():
    assert validate_data.validate_all() == []
