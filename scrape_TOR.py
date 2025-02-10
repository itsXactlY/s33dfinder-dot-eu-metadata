import json
import os
import requests
import time
import re
from stem import Signal
from stem.control import Controller
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urljoin

class ComprehensiveWaybackDownloader:
    def __init__(self, json_file, tor_port=9050, control_port=9051, max_workers=5):
        self.json_file = json_file
        self.tor_port = tor_port
        self.control_port = control_port
        self.max_workers = max_workers
        self.downloaded_urls = set()
        
        os.makedirs('downloads', exist_ok=True)
        os.makedirs('downloads/metadata', exist_ok=True)
        os.makedirs('downloads/resources', exist_ok=True)

    def renew_tor_ip(self):
        try:
            with Controller.from_port(port=self.control_port) as controller:
                controller.authenticate()
                controller.signal(Signal.NEWNYM)
                time.sleep(10)  # ip rotation interval
        except Exception as e:
            print(f"Tor IP renewal error: {e}")

    def is_downloadable_resource(self, url):
        allowed_extensions = ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.html', '.xml', '.txt']
        allowed_domains = ['seedfinder.eu', 'web.archive.org']
        
        parsed_url = urlparse(url)
        return (
            any(ext in url.lower() for ext in allowed_extensions) or 
            any(domain in parsed_url.netloc for domain in allowed_domains)
        )

    def construct_wayback_url(self, original_url, timestamp):
        return f"https://web.archive.org/web/{timestamp}/{original_url}"

    def download_resource(self, url, timestamp):
        if url in self.downloaded_urls or not self.is_downloadable_resource(url):
            return None

        self.downloaded_urls.add(url)
        
        try:
            wayback_url = self.construct_wayback_url(url, timestamp)
            
            proxies = {
                'http': f'socks5h://127.0.0.1:{self.tor_port}',
                'https': f'socks5h://127.0.0.1:{self.tor_port}'
            }

            response = requests.get(
                wayback_url, 
                proxies=proxies,
                timeout=30,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            
            if response.status_code == 200:
                parsed_url = urlparse(url)
                filename = f"{timestamp}_{os.path.basename(parsed_url.path) or 'resource'}"
                filepath = os.path.join('downloads/resources', filename)
                
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                print(f"Downloaded resource: {filename}")
                return filepath
        
        except Exception as e:
            print(f"Resource download failed: {url} - {e}")
        
        return None

    def extract_and_download_resources(self, html_content, base_url, timestamp):
        resource_patterns = [
            r'src=[\'"]([^\'"]+)',
            r'href=[\'"]([^\'"]+)',
            r'url\([\'"]?([^\'")]+)'
        ]

        for pattern in resource_patterns:
            resources = re.findall(pattern, html_content)
            for resource in resources:
                try:
                    if resource.startswith(('http', '//')):
                        full_url = resource if resource.startswith('http') else f'https:{resource}'
                    else:
                        full_url = urljoin(base_url, resource)
                    
                    self.download_resource(full_url, timestamp)
                except Exception as e:
                    print(f"Resource extraction failed: {resource} - {e}")

    def download_full_page(self, entry):
        original_url = entry[2]
        timestamp = entry[1]
        
        try:
            wayback_url = self.construct_wayback_url(original_url, timestamp)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }

            proxies = {
                'http': f'socks5h://127.0.0.1:{self.tor_port}',
                'https': f'socks5h://127.0.0.1:{self.tor_port}'
            }

            response = requests.get(
                wayback_url, 
                proxies=proxies,
                headers=headers, 
                timeout=60
            )
            response.raise_for_status()

            self.extract_and_download_resources(response.text, original_url, timestamp)

            parsed_url = urlparse(original_url)
            filename = f"{timestamp}_{os.path.basename(parsed_url.path) or 'index'}"
            filepath = os.path.join('downloads', filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)

            # Metadata
            metadata = {
                'original_url': original_url,
                'wayback_url': wayback_url,
                'timestamp': timestamp,
                'filepath': filepath
            }
            
            with open(f'downloads/metadata/{filename}.json', 'w') as f:
                json.dump(metadata, f, indent=2)

            print(f"Downloaded: {filename}")
            self.renew_tor_ip()
            return filepath

        except Exception as e:
            print(f"Error downloading {original_url}: {e}")
            return None

    def download_all(self):
        with open(self.json_file, 'r') as f:
            data = json.load(f)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            list(executor.map(self.download_full_page, data))

if __name__ == '__main__':
    downloader = ComprehensiveWaybackDownloader('metadata.json')
    downloader.download_all()
