"""
Test Phase 0 setup — verify folder structure and imports.
"""

import pytest
from pathlib import Path


def test_folder_structure():
    """Verify all required folders exist."""
    required_folders = [
        'app',
        'app/collectors',
        'app/processors',
        'app/analyzers',
        'app/generators',
        'config',
        'data/raw',
        'data/processed',
        'output',
        'tests',
        'logs'
    ]
    
    for folder in required_folders:
        assert Path(folder).exists(), f"Missing folder: {folder}"
        assert Path(folder).is_dir(), f"Not a directory: {folder}"


def test_required_files():
    """Verify required files exist."""
    required_files = [
        'README.md',
        'CLAUDE.md',
        '.gitignore',
        'requirements.txt',
        '.env.example',
        'app.py'
    ]
    
    for file in required_files:
        assert Path(file).exists(), f"Missing file: {file}"
        assert Path(file).is_file(), f"Not a file: {file}"


def test_app_module_imports():
    """Verify app modules can be imported."""
    try:
        import app
        import app.collectors
        import app.processors
        import app.analyzers
        import app.generators
    except ImportError as e:
        pytest.fail(f"Failed to import app modules: {e}")


def test_env_example_content():
    """Verify .env.example has required keys."""
    with open('.env.example', 'r') as f:
        content = f.read()
        required_keys = [
            'ANTHROPIC_API_KEY',
            'DATA_RAW_DIR',
            'DB_PATH'
        ]
        for key in required_keys:
            assert key in content, f"Missing key in .env.example: {key}"


def test_readme_content():
    """Verify README has key sections."""
    with open('README.md', 'r') as f:
        content = f.read()
        required_sections = [
            '# AI RADAR',
            'Architecture',
            'Quick Start',
            'Project Structure'
        ]
        for section in required_sections:
            assert section in content, f"Missing section in README: {section}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
