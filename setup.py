#!/usr/bin/env python3
"""
Setup script for ELIXIR.IT_IMPACT package
"""

from setuptools import setup, find_packages
import os

# Read long description from README
def read_long_description():
    """Read the README.md file for long description."""
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ''

# Read requirements from requirements.txt
def read_requirements():
    """Read requirements from requirements.txt file."""
    req_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    if os.path.exists(req_path):
        with open(req_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []

setup(
    name='elixir-impact',
    version='1.0.0',
    author=['Giuseppe Defazio', 'Vincenzo Angiulli'],
    author_email=['giuseppe.defazio@uniba.it', 'vincenzo.angiulli@uniba.it'],
    description='Bibliometric Impact Assessment System for ELIXIR services and authors',
    long_description=read_long_description(),
    long_description_content_type='text/markdown',
    url='https://github.com/gdefazio/ELIXIR.IT_IMPACT',
    
    # Package configuration
    packages=find_packages(exclude=['test', 'test.*', 'docs', 'docs.*']),
    package_dir={'': '.'},
    
    # Requirements
    install_requires=read_requirements(),
    python_requires='>=3.11',
    
    # Entry points for command-line scripts
    entry_points={
        'console_scripts': [
            'elixir-author-search=source.AuthorAsService:main',
            'elixir-doi-impact=source.DOI2impact:main',
        ],
    },
    
    # Classifiers help users find your project
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Information Analysis',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Operating System :: OS Independent',
    ],
    
    # Additional metadata
    keywords='bibliometrics scopus openalex citations impact-assessment elixir',
    project_urls={
        'Bug Reports': 'https://github.com/gdefazio/ELIXIR.IT_IMPACT/issues',
        'Source': 'https://github.com/gdefazio/ELIXIR.IT_IMPACT',
        'Documentation': 'https://github.com/gdefazio/ELIXIR.IT_IMPACT/tree/main/docs',
    },
    
    # Include package data
    include_package_data=True,
    zip_safe=False,
)
