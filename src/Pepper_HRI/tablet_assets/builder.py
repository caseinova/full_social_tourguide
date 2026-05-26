import os
import webbrowser
import http.server
import socketserver
import threading
import time
import json
import socket
from urllib.parse import urlparse

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from social_robot_interfaces.msg import TspCommand
from social_robot_interfaces.srv import Description, Tours
from ament_index_python.packages import PackageNotFoundError, get_package_share_directory

PACKAGE_NAME = 'pepper_hri'


def get_tablet_assets_dir():
    try:
        return os.path.join(get_package_share_directory(PACKAGE_NAME), 'tablet_assets')
    except PackageNotFoundError:
        return os.path.dirname(os.path.abspath(__file__))


# Global safety anchor for the installed package share, with a source-tree fallback.
SCRIPT_DIR = get_tablet_assets_dir()


class TabletBuilderNode(Node):  

    def __init__(self):
        super().__init__('tablet_builder_node')
        
        # Subscribe to the gesture/tour command topic
        self.subscription = self.create_subscription(
            String,
            '/pepper/explain_exhibit',
            self.listener_callback,
            10)
        
        # Publisher for selected tablet tour waypoints.
        self.tsp_command_publisher = self.create_publisher(
            TspCommand,
            '/tsp_command',
            10)
        self.tour_retrieve_client = self.create_client(Tours, 'tour_retrieve')
        self.retrieve_description_client = self.create_client(Description, 'retrieve_description')
        self.declare_parameter('pepper_ip', '')
        self.declare_parameter('naoqi_port', 9559)
        self.declare_parameter('use_tablet_service', True)
        self.declare_parameter('tablet_base_url', '')
        self.declare_parameter('tablet_port', 8000)
        self.declare_parameter('auto_select_tablet_port', True)
        self.declare_parameter('show_local_browser', False)
        self._tablet_session = None
        self._tablet_service = None
        self._tablet_signal_id = None
        self._touch_signal_ids = []
        self._tablet_lock = threading.Lock()
        self._processed_tablet_events = {}
        self._last_touch_action_time = 0.0
        self.tablet_base_url = ''
        self.current_tablet_page = ''

        self.get_logger().info("Tablet Builder Node is ready.")

    def connect_tablet_service(self):
        if not self.get_parameter('use_tablet_service').value:
            return None

        with self._tablet_lock:
            if self._tablet_service is not None:
                return self._tablet_service

            pepper_ip = str(self.get_parameter('pepper_ip').value).strip()
            if not pepper_ip:
                self.get_logger().warn(
                    "Pepper tablet service is enabled, but 'pepper_ip' is empty.")
                return None

            try:
                import qi

                naoqi_port = int(self.get_parameter('naoqi_port').value)
                session = qi.Session()
                session.connect(f'tcp://{pepper_ip}:{naoqi_port}')
                tablet_service = session.service('ALTabletService')
                self._tablet_session = session
                self._tablet_service = tablet_service
                self._connect_tablet_signal_locked(tablet_service)
                self.get_logger().info(
                    f"Connected to ALTabletService at {pepper_ip}:{naoqi_port}")
                return tablet_service
            except Exception as exc:
                self._tablet_session = None
                self._tablet_service = None
                self._tablet_signal_id = None
                self._touch_signal_ids = []
                self.get_logger().error(f"Could not connect to ALTabletService: {exc}")
                return None

    def _connect_tablet_signal_locked(self, tablet_service):
        if self._tablet_signal_id is not None:
            return

        self._tablet_signal_id = tablet_service.onJSEvent.connect(
            self.handle_tablet_js_event)
        self.get_logger().info("Connected ALTabletService.onJSEvent")
        self._connect_touch_signals_locked(tablet_service)

    def _connect_touch_signals_locked(self, tablet_service):
        if self._touch_signal_ids:
            return

        try:
            signal_id = tablet_service.onTouchDownRatio.connect(
                self.handle_tablet_touch_ratio)
            self._touch_signal_ids.append(('onTouchDownRatio', signal_id))
            self.get_logger().info("Connected ALTabletService.onTouchDownRatio")
        except Exception as exc:
            self.get_logger().warn(
                f"Could not connect ALTabletService.onTouchDownRatio: {exc}")

        try:
            signal_id = tablet_service.onTouchDown.connect(
                self.handle_tablet_touch_down)
            self._touch_signal_ids.append(('onTouchDown', signal_id))
            self.get_logger().info("Connected ALTabletService.onTouchDown")
        except Exception as exc:
            self.get_logger().warn(
                f"Could not connect ALTabletService.onTouchDown: {exc}")

    def handle_tablet_touch_ratio(self, x, y, view_touched):
        self.get_logger().info(
            f"ALTabletService.onTouchDownRatio: x={x:.3f}, y={y:.3f}, view={view_touched}")
        self.handle_tablet_touch_fallback(x, y, 'ratio')

    def handle_tablet_touch_down(self, x, y):
        self.get_logger().info(f"ALTabletService.onTouchDown: x={x}, y={y}")
        norm_x, norm_y = self.normalize_tablet_touch(x, y)
        self.get_logger().info(
            f"Normalized tablet touch: x={norm_x:.3f}, y={norm_y:.3f}, "
            f"page='{self.current_tablet_page}'")
        self.handle_tablet_touch_fallback(norm_x, norm_y, 'raw')

    def normalize_tablet_touch(self, x, y):
        scale_factor = 1.34
        tablet_service = self._tablet_service
        if tablet_service is not None:
            try:
                scale_factor = float(tablet_service.getOnTouchScaleFactor())
            except Exception as exc:
                self.get_logger().warn(
                    f"ALTabletService.getOnTouchScaleFactor failed: {exc}")

        # Pepper's browser view reports scaled 1280x800 coordinates by default.
        width = 1280.0 * scale_factor
        height = 800.0 * scale_factor
        norm_x = max(0.0, min(1.0, float(x) / width))
        norm_y = max(0.0, min(1.0, float(y) / height))
        return norm_x, norm_y

    def handle_tablet_touch_fallback(self, norm_x, norm_y, source):
        now = time.time()
        if now - self._last_touch_action_time < 0.8:
            return

        page = os.path.basename(urlparse(self.current_tablet_page).path)
        self.get_logger().info(
            f"Evaluating touch fallback from {source}: page='{page}', "
            f"x={norm_x:.3f}, y={norm_y:.3f}")

        if page != 'index.html' or norm_y < 0.78:
            return

        # Bottom-left control row on index.html:
        # Tour Select | - Text Size | + Text Size. Keep ranges intentionally
        # conservative so zoom presses do not trigger navigation.
        if 0.00 <= norm_x < 0.12:
            self._last_touch_action_time = now
            self.get_logger().warn(
                "Touch fallback matched Tour Select button; navigating to menu.html")
            self.show_tablet_page('menu.html')
        elif 0.12 <= norm_x < 0.25:
            self._last_touch_action_time = now
            self.get_logger().warn(
                "Touch fallback matched decrease text size button")
            self.adjust_tablet_text_size(-5)
        elif 0.25 <= norm_x < 0.40:
            self._last_touch_action_time = now
            self.get_logger().warn(
                "Touch fallback matched increase text size button")
            self.adjust_tablet_text_size(5)

    def adjust_tablet_text_size(self, change):
        script = """
            (function () {
                if (typeof adjustTextSize === 'function') {
                    adjustTextSize(__CHANGE__);
                    if (window.ALTabletBinding && window.ALTabletBinding.raiseEvent) {
                        var textBox = document.querySelector('.text-box');
                        var size = textBox ? window.getComputedStyle(textBox).fontSize : '';
                        window.ALTabletBinding.raiseEvent(JSON.stringify({
                            type: 'text_size_changed',
                            change: __CHANGE__,
                            fontSize: size
                        }));
                    }
                    return;
                }

                var textBox = document.querySelector('.text-box');
                if (!textBox) return;
                var currentSize = parseInt(window.getComputedStyle(textBox).fontSize, 10) || 50;
                var newSize = currentSize + __CHANGE__;
                if (newSize >= 20 && newSize <= 100) {
                    textBox.style.fontSize = newSize + 'px';
                }
                if (window.ALTabletBinding && window.ALTabletBinding.raiseEvent) {
                    window.ALTabletBinding.raiseEvent(JSON.stringify({
                        type: 'text_size_changed',
                        change: __CHANGE__,
                        fontSize: textBox.style.fontSize
                    }));
                }
            })();
        """.replace('__CHANGE__', str(int(change)))
        self.execute_tablet_js(script, f"adjust text size by {change}")

    def execute_tablet_js(self, script, description):
        tablet_service = self.connect_tablet_service()
        if tablet_service is None:
            return False

        try:
            tablet_service.executeJS(script)
            self.get_logger().info(f"ALTabletService.executeJS({description})")
            return True
        except Exception as exc:
            self.get_logger().error(
                f"ALTabletService.executeJS({description}) failed: {exc}")
            return False

    def handle_tablet_js_event(self, event):
        self.get_logger().info(f"ALTabletService.onJSEvent: {event}")

        try:
            data = json.loads(event)
        except Exception:
            data = {'type': 'raw', 'value': event}

        self.handle_tablet_event(data, 'onJSEvent')

    def handle_tablet_event(self, data, source):
        event_type = data.get('type')
        event_id = data.get('eventId')
        if event_id:
            now = time.time()
            self._processed_tablet_events = {
                key: timestamp
                for key, timestamp in self._processed_tablet_events.items()
                if now - timestamp < 10.0
            }
            if event_id in self._processed_tablet_events:
                self.get_logger().info(
                    f"Skipping duplicate tablet event from {source}: {event_id}")
                return
            self._processed_tablet_events[event_id] = now

        self.get_logger().info(
            f"Handling tablet event from {source}: type={event_type}, data={data}")

        try:
            if event_type == 'navigate':
                page = str(data.get('page', '')).strip()
                button = str(data.get('button', 'unknown')).strip()
                self.get_logger().info(
                    f"Tablet button '{button}' requested page '{page}'")
                self.show_tablet_page(page)
            elif event_type == 'tour_submit':
                waypoints = self.parse_tsp_waypoints(data)
                self.publish_tsp_command(waypoints)
            elif event_type == 'diagnostic':
                self.get_logger().info(f"Tablet diagnostic event: {data}")
                self.report_tablet_diagnostic(data)
            elif event_type == 'text_size_changed':
                self.get_logger().info(f"Tablet text size changed: {data}")
            else:
                self.get_logger().warn(f"Unhandled tablet JS event: {event}")
        except Exception as exc:
            self.get_logger().error(f"Failed to handle tablet JS event: {exc}")

    def report_tablet_diagnostic(self, data):
        current_url = str(data.get('url', ''))
        expected_url = str(data.get('expectedUrl', ''))
        button_count = int(data.get('buttonCount', 0))
        fetch_status = data.get('fetchStatus', 'unknown')
        fetch_error = data.get('fetchError', '')

        if current_url.startswith('data:text/html,chromewebdata') or button_count == 0:
            self.get_logger().error(
                "Pepper tablet did not load the HRI page. "
                f"current_url='{current_url}', expected_url='{expected_url}', "
                f"button_count={button_count}, fetch_status='{fetch_status}', "
                f"fetch_error='{fetch_error}'. "
                "The tablet is showing Chromium's error page, so button presses cannot reach the app.")
            self.get_logger().error(
                "Check that Pepper can reach tablet_base_url from the robot/tablet network. "
                "If the inferred URL is wrong, set tablet_builder_node.ros__parameters.tablet_base_url "
                "to a reachable URL such as http://<laptop-ip-on-pepper-wifi>:8000.")
        else:
            self.get_logger().info(
                f"Pepper tablet page loaded OK: current_url='{current_url}', "
                f"button_count={button_count}, fetch_status='{fetch_status}'")

    def handle_tablet_log(self, data):
        level = str(data.get('level', 'info')).lower()
        message = str(data.get('message', '')).strip()
        payload = data.get('payload')
        text = f"Tablet JS log: {message}"
        if payload is not None:
            text = f"{text} | payload={payload}"

        if level == 'error':
            self.get_logger().error(text)
        elif level in ('warn', 'warning'):
            self.get_logger().warn(text)
        else:
            self.get_logger().info(text)

    def safe_page_url(self, page):
        parsed_page = urlparse(page)
        if parsed_page.scheme in ('http', 'https'):
            return self.cache_bust_url(page)

        safe_page = page.lstrip('/')
        if not safe_page:
            raise ValueError("Tablet page cannot be empty")
        if '..' in safe_page.split('/'):
            raise ValueError(f"Tablet page is not allowed: {page}")
        if not self.tablet_base_url:
            raise ValueError("Tablet base URL is not configured yet")

        return self.cache_bust_url(f"{self.tablet_base_url}/{safe_page}")

    def cache_bust_url(self, url):
        separator = '&' if '?' in url else '?'
        return f"{url}{separator}tablet_ts={int(time.time() * 1000)}"

    def show_tablet_page(self, page):
        tablet_service = self.connect_tablet_service()
        if tablet_service is None:
            return False

        url = self.safe_page_url(page)

        try:
            tablet_service.cleanWebview()
            self.get_logger().info("ALTabletService.cleanWebview()")
        except Exception as exc:
            self.get_logger().warn(f"ALTabletService.cleanWebview failed: {exc}")

        try:
            tablet_service.showWebview(url)
            self.current_tablet_page = page
            self.get_logger().info(f"ALTabletService.showWebview({url})")
            self.inject_tablet_diagnostics(tablet_service, url)
            return True
        except Exception as exc:
            self.get_logger().error(f"ALTabletService.showWebview failed: {exc}")

        try:
            tablet_service.loadUrl(url)
            tablet_service.showWebview()
            self.current_tablet_page = page
            self.get_logger().info(f"ALTabletService.loadUrl({url})")
            self.inject_tablet_diagnostics(tablet_service, url)
            return True
        except Exception as exc:
            self.get_logger().error(f"ALTabletService.loadUrl failed: {exc}")
            with self._tablet_lock:
                self._tablet_session = None
                self._tablet_service = None
                self._tablet_signal_id = None
            return False

    def clear_tablet_webview(self):
        tablet_service = self.connect_tablet_service()
        if tablet_service is None:
            return False

        cleared = True
        try:
            tablet_service.hideWebview()
            self.get_logger().info("ALTabletService.hideWebview() before initial page")
        except Exception as exc:
            cleared = False
            self.get_logger().warn(f"ALTabletService.hideWebview failed before initial page: {exc}")

        try:
            tablet_service.cleanWebview()
            self.get_logger().info("ALTabletService.cleanWebview() before initial page")
        except Exception as exc:
            cleared = False
            self.get_logger().warn(f"ALTabletService.cleanWebview failed before initial page: {exc}")

        self.current_tablet_page = ''
        return cleared

    def inject_tablet_diagnostics(self, tablet_service, url):
        def run_diagnostics():
            time.sleep(2.0)
            script = """
                (function () {
                    function send(payload) {
                        if (window.ALTabletBinding && window.ALTabletBinding.raiseEvent) {
                            window.ALTabletBinding.raiseEvent(JSON.stringify(payload));
                        }
                    }

                    var payload = {
                        type: 'diagnostic',
                        url: window.location.href,
                        expectedUrl: __EXPECTED_URL__,
                        hasALTabletBinding: !!window.ALTabletBinding,
                        hasRaiseEvent: !!(window.ALTabletBinding && window.ALTabletBinding.raiseEvent),
                        readyState: document.readyState,
                        buttonCount: document.querySelectorAll('button').length,
                        fetchStatus: 'not_started',
                        fetchError: ''
                    };

                    if (window.fetch) {
                        fetch(__EXPECTED_URL__, { cache: 'no-store', mode: 'no-cors' })
                            .then(function (response) {
                                payload.fetchStatus = 'resolved:' + response.type;
                                send(payload);
                            })
                            .catch(function (error) {
                                payload.fetchStatus = 'rejected';
                                payload.fetchError = error && error.message ? error.message : String(error);
                                send(payload);
                            });
                    } else {
                        payload.fetchStatus = 'fetch_unavailable';
                        send(payload);
                    }
                })();
            """.replace('__EXPECTED_URL__', json.dumps(url))

            try:
                tablet_service.executeJS(script)
                self.get_logger().info("ALTabletService.executeJS(tablet diagnostics)")
            except Exception as exc:
                self.get_logger().warn(
                    f"ALTabletService.executeJS diagnostics failed: {exc}")

        threading.Thread(target=run_diagnostics, daemon=True).start()

    def publish_tsp_command(self, waypoints):
        msg = TspCommand()
        msg.waypoints = waypoints
        self.tsp_command_publisher.publish(msg)
        self.get_logger().info(f"Published TSP command to /tsp_command: {waypoints}")

    def disconnect_tablet_service(self):
        with self._tablet_lock:
            tablet_service = self._tablet_service
            signal_id = self._tablet_signal_id
            touch_signal_ids = list(self._touch_signal_ids)
            self._tablet_signal_id = None
            self._touch_signal_ids = []
            self._tablet_service = None
            self._tablet_session = None

        if tablet_service is None:
            return

        if signal_id is not None:
            try:
                tablet_service.onJSEvent.disconnect(signal_id)
                self.get_logger().info("Disconnected ALTabletService.onJSEvent")
            except Exception as exc:
                self.get_logger().warn(
                    f"Failed to disconnect ALTabletService.onJSEvent: {exc}")

        for signal_name, touch_signal_id in touch_signal_ids:
            try:
                getattr(tablet_service, signal_name).disconnect(touch_signal_id)
                self.get_logger().info(f"Disconnected ALTabletService.{signal_name}")
            except Exception as exc:
                self.get_logger().warn(
                    f"Failed to disconnect ALTabletService.{signal_name}: {exc}")

    def listener_callback(self, msg):
        command = msg.data.strip()
        self.get_logger().info(f"Rebuilding page for command: {command}")
        
        print(command)
        if self.build_page(command):
            self.show_tablet_page('index.html')

    def build_page(self, command_name):
        # Load the manifest using absolute positioning
        manifest_path = os.path.join(SCRIPT_DIR, 'exhibition_commands.json')
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        if command_name not in manifest:
            print(f"Error: Command '{command_name}' not found in exhibition_commands.json")
            return False

        config = manifest[command_name]

        # Convert raw config paths to absolute paths for Python filesystem checks
        img_folder_abs = os.path.join(SCRIPT_DIR, config['image_folder'])
        text_file_abs = os.path.join(SCRIPT_DIR, config['text_file'])

        # Name of header derived safely from path base
        folder_name = os.path.basename(img_folder_abs)
        clean_title = folder_name.replace('_', ' ').title()

        # Count how many images are in the target folder safely
        if os.path.exists(img_folder_abs):
            images_list = [f for f in os.listdir(img_folder_abs) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
            num_images = len(images_list)
        else:
            num_images = 0

        print(f"Detected image count: {num_images}")

        # If 3 or more images, turn on the scroll animation
        scroll_class = "animate-scroll" if num_images >= 2 else "static-gallery"
        
        # Read the artifact text file safely
        with open(text_file_abs, 'r') as f:
            description = f.read()

        # Gather all images from the specified folder
        valid_extensions = ('.webp', '.jpeg', '.jpg', '.gif', '.png')
        
        gallery_html = ""
        if os.path.exists(img_folder_abs):
            for filename in sorted(os.listdir(img_folder_abs)):
                if filename.lower().endswith(valid_extensions):
                    # For the browser source tag, keep the path relative to the server root
                    rel_path = os.path.join(config['image_folder'], filename)
                    gallery_html += f'<img src="{rel_path}" style="width:100%; margin-bottom:20px;">\n'
        else:
            print(f"Warning: Folder {img_folder_abs} not found.")

        # Assemble the final HTML using absolute template paths
        layout_path = os.path.join(SCRIPT_DIR, 'layout.html')
        with open(layout_path, 'r') as f:
            template = f.read()

        final_html = template.replace('{{description_text}}', description)
        final_html = final_html.replace('{{image_gallery_html}}', gallery_html)
        final_html = final_html.replace('{{artifact_title}}', clean_title)
        final_html = final_html.replace('{{scroll_class}}', scroll_class)

        # Output index.html exactly where layout.html lives
        index_path = os.path.join(SCRIPT_DIR, 'index.html')
        with open(index_path, 'w') as f:
            f.write(final_html)
        
        print(f"index.html rebuilt for: {command_name}")

        # Write current state file safely
        state_data = {
            "command": command_name,
            "timestamp": time.time()
        }

        state_path = os.path.join(SCRIPT_DIR, 'current_state.json')
        with open(state_path, 'w') as f:
            json.dump(state_data, f)
    
        print(f"Signal sent for {command_name}")
        return True

    def parse_tsp_waypoints(self, data):
        selected_commands = data.get('waypoints', data.get('commands'))
        if not isinstance(selected_commands, list):
            raise ValueError("Expected JSON field 'commands' or 'waypoints' to be a list")

        waypoints = []
        for command in selected_commands:
            if isinstance(command, int):
                waypoint = command
            elif isinstance(command, str):
                if command.startswith('artifact_'):
                    waypoint = int(command.rsplit('_', 1)[1]) - 1
                else:
                    waypoint = int(command)
            else:
                raise ValueError(f"Unsupported waypoint value: {command!r}")

            if waypoint < 0:
                raise ValueError(f"Waypoint index must be non-negative: {waypoint}")

            waypoints.append(waypoint)

        return waypoints

    def call_service(self, client, service_name, request, timeout_sec=2.0):
        if not client.wait_for_service(timeout_sec=timeout_sec):
            raise RuntimeError(f"Service '{service_name}' is not available")

        event = threading.Event()
        future = client.call_async(request)
        future.add_done_callback(lambda _: event.set())

        if not event.wait(timeout_sec):
            raise RuntimeError(f"Timed out waiting for service '{service_name}'")

        result = future.result()
        if result is None:
            raise RuntimeError(f"Service '{service_name}' returned no result")

        return result

    def get_waypoint_description(self, waypoint_idx):
        request = Description.Request()
        request.idx = waypoint_idx
        response = self.call_service(
            self.retrieve_description_client,
            'retrieve_description',
            request)
        return response.description.data

    def get_available_waypoints(self):
        request = Tours.Request()
        request.idx = 0
        response = self.call_service(
            self.tour_retrieve_client,
            'tour_retrieve',
            request)

        waypoints = []
        for waypoint_idx, _ in enumerate(response.tour):
            raw_description = self.get_waypoint_description(waypoint_idx)
            name, separator, description = raw_description.partition('|')
            name = name.strip()
            description = description.strip() if separator else ''

            waypoints.append({
                'idx': waypoint_idx,
                'name': name or f'Waypoint {waypoint_idx + 1}',
                'description': description,
            })

        return waypoints


def get_reachable_host_ip(node):
    pepper_ip = str(node.get_parameter('pepper_ip').value).strip()
    if pepper_ip:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect((pepper_ip, int(node.get_parameter('naoqi_port').value)))
            host_ip = sock.getsockname()[0]
            sock.close()
            return host_ip
        except Exception as exc:
            node.get_logger().warn(
                f"Could not infer host IP from Pepper route: {exc}")

    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return 'localhost'


def create_tablet_server(node, handler_class):
    start_port = int(node.get_parameter('tablet_port').value)
    auto_select = bool(node.get_parameter('auto_select_tablet_port').value)
    candidate_ports = [start_port]
    if auto_select:
        candidate_ports.extend(range(start_port + 1, start_port + 21))

    last_error = None
    for port in candidate_ports:
        try:
            httpd = socketserver.TCPServer(("", port), handler_class)
            if port != start_port:
                node.get_logger().warn(
                    f"Tablet HTTP port {start_port} is busy; using {port} instead.")
            return httpd, port
        except OSError as exc:
            last_error = exc
            if exc.errno != 98:
                raise
            node.get_logger().warn(f"Tablet HTTP port {port} is already in use.")

    raise last_error


# Global server loop runner function (cleanly isolated from Node class scopes)
def start_server(node):
    # Force the local server context directory straight to our root assets folder
    os.chdir(SCRIPT_DIR)

    # Define custom request handler class inline to access the 'node' reference directly
    class ROSRequestHandler(http.server.SimpleHTTPRequestHandler):
        def send_json(self, status_code, payload):
            self.send_response(status_code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode('utf-8'))

        def read_json_body(self):
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            if not post_data:
                return {}
            return json.loads(post_data.decode('utf-8'))

        def do_GET(self):
            request_path = urlparse(self.path).path
            node.get_logger().info(
                f"Tablet HTTP GET {self.path} routed as {request_path}")
            if request_path == '/health':
                self.send_json(200, {
                    'status': 'ok',
                    'tablet_base_url': node.tablet_base_url,
                    'script_dir': SCRIPT_DIR,
                })
            elif request_path == '/tour_waypoints':
                try:
                    waypoints = node.get_available_waypoints()
                    node.get_logger().info(
                        f"Sending {len(waypoints)} tour waypoints to tablet")
                    self.send_json(200, {'waypoints': waypoints})
                except Exception as e:
                    node.get_logger().error(f"Failed to retrieve tour waypoints: {str(e)}")
                    self.send_json(500, {'error': str(e)})
            else:
                super().do_GET()

        def do_POST(self):
            request_path = urlparse(self.path).path
            node.get_logger().info(
                f"Tablet HTTP POST {self.path} routed as {request_path}")
            if request_path == '/tour_retrieve':
                try:
                    data = self.read_json_body()
                    
                    waypoints = node.parse_tsp_waypoints(data)
                    node.publish_tsp_command(waypoints)

                    self.send_json(200, {
                        "status": "published",
                        "topic": "/tsp_command",
                        "waypoints": waypoints
                    })
                    
                except Exception as e:
                    node.get_logger().error(f"Failed to parse POST data: {str(e)}")
                    self.send_json(400, {'error': str(e)})
            elif request_path == '/tablet_log':
                try:
                    data = self.read_json_body()
                    node.handle_tablet_log(data)
                    self.send_json(200, {'status': 'logged'})
                except Exception as e:
                    node.get_logger().error(f"Failed to parse tablet log: {str(e)}")
                    self.send_json(400, {'error': str(e)})
            elif request_path == '/tablet_event':
                try:
                    data = self.read_json_body()
                    node.handle_tablet_event(data, 'http_fallback')
                    self.send_json(200, {'status': 'handled'})
                except Exception as e:
                    node.get_logger().error(f"Failed to handle tablet event fallback: {str(e)}")
                    self.send_json(400, {'error': str(e)})
            else:
                self.send_response(404)
                self.end_headers()

    socketserver.TCPServer.allow_reuse_address = True

    try:
        httpd, selected_port = create_tablet_server(node, ROSRequestHandler)
    except OSError as exc:
        node.get_logger().error(f"Could not start tablet HTTP server: {exc}")
        return

    configured_base_url = str(node.get_parameter('tablet_base_url').value).strip()
    if configured_base_url:
        node.tablet_base_url = configured_base_url.rstrip('/')
        configured_port = urlparse(node.tablet_base_url).port
        if configured_port is not None and configured_port != selected_port:
            node.get_logger().warn(
                f"Configured tablet_base_url uses port {configured_port}, "
                f"but local tablet server is listening on {selected_port}.")
    else:
        node.tablet_base_url = f"http://{get_reachable_host_ip(node)}:{selected_port}"

    with httpd:
        print(f"Serving at http://localhost:{selected_port}")
        node.get_logger().info(f"Pepper tablet base URL: {node.tablet_base_url}")
        node.get_logger().info(
            f"Pepper tablet health check URL: {node.tablet_base_url}/health")
        
        def open_browser():
            time.sleep(0.5)
            if node.get_parameter('show_local_browser').value:
                print("Opening browser...")
                webbrowser.open(f"http://localhost:{selected_port}/index.html")
            node.clear_tablet_webview()
            node.show_tablet_page('index.html')

        ROSRequestHandler.extensions_map.update({
            '.webp': 'image/webp',
        })
        threading.Thread(target=open_browser).start()
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            httpd.shutdown()
            print("\nServer stopped.")


def main(args=None):
    rclpy.init(args=args)
    node = TabletBuilderNode()
    
    # Target our standalone global server handler function
    threading.Thread(target=start_server, args=(node,), daemon=True).start()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.disconnect_tablet_service()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
