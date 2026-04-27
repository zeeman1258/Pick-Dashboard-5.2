from flask import Flask, request, jsonify, render_template_string, Response, session
import requests, re, sqlite3, os, json, signal, threading, webbrowser, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlencode
import html
from html.parser import HTMLParser

appversion = '5.1.15'

# NOTE: Full app.py content — see attached source file for complete implementation
# This repository was initialized from Pick Dashboard 5.1.15 source.
# Upload the complete app.py from the release zip to replace this placeholder.
