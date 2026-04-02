from setuptools import setup, find_packages

setup(
    name="rhetoric-lint",
    version="0.1.0",
    description="A lightweight Markdown linter focused on rhetorical quality",
    author="Rhetoric Linter Contributors",
    python_requires=">=3.8",
    packages=["rhetoric_lint", "rhetoric_lint.rules"],
    install_requires=[
        "mistletoe",
        "spacy",
        "spacy-wordnet",
        "typer",
        "nltk",
    ],
    extras_require={
        "yaml": ["pyyaml"],
        "dev": ["pytest"],
    },
    entry_points={
        "console_scripts": [
            "rhetoric-lint=rhetoric_lint.main:app",
        ],
    },
)
