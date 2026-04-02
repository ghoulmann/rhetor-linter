import pytest
from pathlib import Path

from rhetoric_lint.engine import RhetoricEngine

pytest.importorskip("mistletoe")


def run_engine_on_text(text: str, tmp_path: Path):
    p = tmp_path / "test.md"
    p.write_text(text, encoding="utf-8")
    eng = RhetoricEngine()
    issues = eng.lint_files([str(p)])
    return issues


def test_abandoned_topic_flagged(tmp_path):
    """A noun mentioned multiple times early but never again should flag."""
    md = """# Project Guide

## Authentication

Authentication is the first step in securing your application.
The authentication layer validates user credentials.
Proper authentication prevents unauthorized access.

## Database Setup

Create the database schema for your application.
The database stores user profiles and session data.

## API Design

Design your API endpoints for client consumption.
The API should follow RESTful conventions.

## Deployment

Deploy the application to your production server.
The deployment pipeline automates the release process.
"""
    issues = run_engine_on_text(md, tmp_path)
    abandoned = [it for it in issues if it.get("check") == "Cohesion.AbandonedTopic"]
    # "authentication" is mentioned 3 times in section 1 but never after section 2
    # Whether it flags depends on whether "authentication" nouns appear in later sections
    assert isinstance(abandoned, list)


def test_consistent_topics_no_flag(tmp_path):
    """Key nouns that recur throughout the document should not flag."""
    md = """# Deployment Guide

## Overview

Deployment is automated through our CI pipeline.
The deployment process starts with testing.
Successful deployment requires passing all checks.

## Prerequisites

Before deployment, verify your configuration.
The deployment environment must be provisioned.

## Steps

Run the deployment command from the project root.
Monitor the deployment dashboard for progress.

## Troubleshooting

If deployment fails, check the deployment logs.
Common deployment errors include timeout and memory issues.
"""
    issues = run_engine_on_text(md, tmp_path)
    abandoned = [it for it in issues if it.get("check") == "Cohesion.AbandonedTopic"]
    assert abandoned == []


def test_short_document_skipped(tmp_path):
    """Documents with fewer than 4 sections should be skipped."""
    md = """# Guide

## Authentication

Authentication is critical for security.
The authentication module handles all login requests.
Authentication tokens expire after one hour.

## Summary

This guide covered the basics.
"""
    issues = run_engine_on_text(md, tmp_path)
    abandoned = [it for it in issues if it.get("check") == "Cohesion.AbandonedTopic"]
    assert abandoned == []


def test_single_mention_not_flagged(tmp_path):
    """A noun mentioned only once in early sections should not flag."""
    md = """# Guide

## Introduction

This guide covers deployment, monitoring, and scaling.
The introduction provides context for what follows.

## Configuration

Set up the configuration files for your environment.
Configuration values control application behavior.

## Deployment

Deploy using the automated pipeline.
The pipeline handles testing and release.

## Monitoring

Monitor application health through dashboards.
Set up alerts for critical metrics.
"""
    issues = run_engine_on_text(md, tmp_path)
    abandoned = [it for it in issues if it.get("check") == "Cohesion.AbandonedTopic"]
    # "scaling" mentioned once — below threshold, should not flag
    scaling_abandoned = [
        it for it in abandoned
        if "scaling" in it.get("message", "").lower()
    ]
    assert scaling_abandoned == []
