#!/usr/bin/env python3
"""Module d'execution d'actions pour l'agent CLI"""
import os, subprocess, sys, json, signal, time, re, builtins, logging
from datetime import datetime

from pathlib import Path
from typing import Dict, Any, Generator
from uploader import FileUploader
from src.core.mcp_manager import MCPManager

mcp_mgr = MCPManager()

class ActionExecutor:
    def __init__(self, workspace="./workspace", bridge=None):