"""
FastAPI Backend for OBus MOA Runtime
Supports Tarot cards, Solomon's Keys, Decks, and routing
"""
from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
import json
import typing
from typing import List, Literal, Optional
import mimetypes
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
import asyncio
import base64
import copy
import html
import hashlib
import hmac
import functools
import ipaddress
from contextlib import contextmanager
import shutil
import socket
import subprocess
import threading
import time
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid

from backend.tentacle_worms import WORM_ROLES, run_tentacle_audit
from backend import access_gate
from backend.aui import build_manifest
from backend.aui_events import ROUTE_EVENTS, safe_route_id
