import argparse
import fcntl
import os
import sqlite3
import sys
import tempfile
import threading
import yaml

import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import OccupancyGrid
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QFont
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from social_robot_interfaces.msg import TspCommand
from social_robot_interfaces.srv import Tours
from std_msgs.msg import String

CIRCLE_RADIUS = 14

_WS_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..")
)
_SEARCH_DIRS = [
    os.getcwd(),
    os.path.expanduser("~"),
    _WS_ROOT,
    os.path.join(os.path.expanduser("~"), "Development", "robot_gpt", "turtlebot_social_guide"),
]


def _find_file(filename):
    for d in _SEARCH_DIRS:
        p = os.path.join(d, filename)
        if os.path.isfile(p):
            return p
    return None


# ---------------------------------------------------------------------------
# Map loading
# ---------------------------------------------------------------------------

def _load_map_from_yaml(yaml_path: str) -> OccupancyGrid:
    with open(yaml_path) as f:
        cfg = yaml.safe_load(f)
    yaml_dir = os.path.dirname(os.path.abspath(yaml_path))
    pgm_path = os.path.join(yaml_dir, cfg["image"])
    resolution = float(cfg["resolution"])
    origin = cfg["origin"]
    negate = int(cfg.get("negate", 0))
    occ_thresh = float(cfg.get("occupied_thresh", 0.65))
    free_thresh = float(cfg.get("free_thresh", 0.25))

    with open(pgm_path, "rb") as f:
        raw = f.read()
    lines, i = [], 0
    while len(lines) < 3:
        j = raw.index(b"\n", i)
        line = raw[i:j].decode("ascii").strip()
        i = j + 1
        if not line.startswith("#"):
            lines.append(line)
    w, h = map(int, lines[1].split())
    maxval = int(lines[2])
    pixel_data = np.frombuffer(raw[i:], dtype=np.uint8).reshape((h, w))
    prob = pixel_data.astype(np.float32) / maxval
    if negate:
        prob = 1.0 - prob
    og_data = np.full((h, w), -1, dtype=np.int8)
    og_data[prob >= occ_thresh] = 100
    og_data[prob <= free_thresh] = 0

    og = OccupancyGrid()
    og.info.width = w
    og.info.height = h
    og.info.resolution = resolution
    og.info.origin.position.x = float(origin[0])
    og.info.origin.position.y = float(origin[1])
    og.info.origin.position.z = 0.0
    og.info.origin.orientation.w = 1.0
    og.data = og_data.flatten().tolist()
    return og


# ---------------------------------------------------------------------------
# Waypoint loading
# ---------------------------------------------------------------------------

def _load_waypoints_from_db(db_path: str):
    waypoints = []
    try:
        con = sqlite3.connect(db_path)
        rows = con.execute("SELECT px,py,pz,qx,qy,qz,qw FROM tours").fetchall()
        con.close()
        for row in rows:
            ps = PoseStamped()
            ps.header.frame_id = "map"
            ps.pose.position.x = float(row[0])
            ps.pose.position.y = float(row[1])
            ps.pose.position.z = float(row[2])
            ps.pose.orientation.x = float(row[3])
            ps.pose.orientation.y = float(row[4])
            ps.pose.orientation.z = float(row[5])
            ps.pose.orientation.w = float(row[6])
            waypoints.append(ps)
    except Exception as e:
        print(f"[tsp_gui] DB load failed ({db_path}): {e}")
    return waypoints


# ---------------------------------------------------------------------------
# ROS node
# ---------------------------------------------------------------------------

class TspGuiNode(Node):
    def __init__(self):
        super().__init__("tsp_gui_node")
        self.map_msg = None
        self.waypoints = []
        self._window = None
        self._pending_utterance = ""

        live_map_qos = QoSProfile(depth=1)
        live_map_qos.reliability = ReliabilityPolicy.RELIABLE

        latched_map_qos = QoSProfile(depth=1)
        latched_map_qos.reliability = ReliabilityPolicy.RELIABLE
        latched_map_qos.durability = DurabilityPolicy.TRANSIENT_LOCAL

        self.map_sub = self.create_subscription(
            OccupancyGrid, "/map", self._map_cb, live_map_qos
        )
        self.latched_map_sub = self.create_subscription(
            OccupancyGrid, "/map", self._map_cb, latched_map_qos
        )
        self.tsp_pub = self.create_publisher(TspCommand, "/tsp_command", 10)
        self.cli = self.create_client(Tours, "tour_retrieve")
        # Subscription to trigger window display — set up after window is created
        self._show_sub = None

    def _map_cb(self, msg):
        self.map_msg = msg
        if self._window is not None:
            self._window.request_map_refresh()

    def fetch_waypoints(self, db_fallback=None):
        if self.cli.wait_for_service(timeout_sec=5.0):
            req = Tours.Request()
            req.idx = 0
            future = self.cli.call_async(req)
            rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)
            if future.result() is not None:
                self.waypoints = future.result().tour
                self.get_logger().info(f"Fetched {len(self.waypoints)} waypoints from service")

        if not self.waypoints:
            db_path = db_fallback or _find_file("tours.db")
            if db_path:
                self.waypoints = _load_waypoints_from_db(db_path)
                self.get_logger().info(
                    f"Loaded {len(self.waypoints)} waypoints from DB: {db_path}"
                )
            else:
                self.get_logger().warning("No waypoints found")

    def wait_for_map(self, timeout=5.0, map_yaml_fallback=None):
        import time
        start = time.time()
        while self.map_msg is None and time.time() - start < timeout:
            rclpy.spin_once(self, timeout_sec=0.2)

        if self.map_msg is None:
            yaml_path = map_yaml_fallback or _find_file("map.yaml")
            if yaml_path:
                try:
                    self.map_msg = _load_map_from_yaml(yaml_path)
                    self.get_logger().info(f"Loaded map from file: {yaml_path}")
                except Exception as e:
                    self.get_logger().warning(f"Map file load failed: {e}")

    def set_window(self, window):
        self._window = window
        self._show_sub = self.create_subscription(
            String, "/tsp_gui/show", self._on_show_trigger, 10
        )
        self.get_logger().info("TSP GUI node ready — listening on /tsp_gui/show")

    def _on_show_trigger(self, msg):
        if self._window is None:
            return

        # Message data is the original utterance (or "show" for manual triggers)
        self._pending_utterance = msg.data if msg.data != "show" else ""
        self.refresh_waypoints_then_show()

    def refresh_waypoints_then_show(self):
        if not self.cli.wait_for_service(timeout_sec=0.5):
            self.get_logger().warning(
                "tour_retrieve service is not available; showing existing waypoint list"
            )
            self._window.request_show()
            return

        req = Tours.Request()
        req.idx = 0
        future = self.cli.call_async(req)
        future.add_done_callback(self._on_waypoints_refreshed)

    def _on_waypoints_refreshed(self, future):
        try:
            result = future.result()
        except Exception as e:
            self.get_logger().warning(
                f"tour_retrieve refresh failed; showing existing waypoint list: {e}"
            )
            result = None

        if result is not None:
            self.waypoints = list(result.tour)
            self.get_logger().info(
                f"Refreshed {len(self.waypoints)} waypoints from tour_retrieve"
            )

        if self._window is not None:
            self._window.request_show()

    def publish_tsp(self, indices):
        msg = TspCommand()
        msg.waypoints = [int(i) for i in indices]
        self.tsp_pub.publish(msg)
        self.get_logger().info(f"Published TspCommand: {msg.waypoints}")


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _occupancy_grid_to_image(og: OccupancyGrid) -> QImage:
    data = np.array(og.data, dtype=np.int16).reshape(og.info.height, og.info.width)
    rgb = np.full((og.info.height, og.info.width, 3), 205, dtype=np.uint8)
    rgb[data == 0] = [255, 255, 255]
    rgb[data == 100] = [0, 0, 0]
    rgb = np.flipud(rgb)
    h, w, _ = rgb.shape
    return QImage(rgb.tobytes(), w, h, 3 * w, QImage.Format_RGB888)


def _world_to_pixel(wx, wy, info, scale: float):
    origin = info.origin.position
    px = int((wx - origin.x) / info.resolution * scale)
    py = int((info.height - (wy - origin.y) / info.resolution) * scale)
    return px, py


# ---------------------------------------------------------------------------
# Qt widgets
# ---------------------------------------------------------------------------

class MapWidget(QLabel):
    def __init__(self, pixmap, waypoints, map_info, scale: float, parent=None):
        super().__init__(parent)
        self._base = pixmap
        self._info = map_info
        self._scale = scale
        self._waypoints = waypoints
        self._selected = []
        self._on_change = lambda: None
        self._wp_pixels = [
            _world_to_pixel(wp.pose.position.x, wp.pose.position.y, map_info, scale)
            for wp in waypoints
        ]
        self.setFixedSize(pixmap.width(), pixmap.height())
        self._render()

    def set_change_callback(self, cb):
        self._on_change = cb

    def _render(self):
        R = CIRCLE_RADIUS
        canvas = QPixmap(self._base)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)

        if len(self._selected) > 1:
            painter.setPen(QPen(QColor(255, 165, 0), 2, Qt.SolidLine))
            for a, b in zip(self._selected, self._selected[1:]):
                ax, ay = self._wp_pixels[a]
                bx, by = self._wp_pixels[b]
                painter.drawLine(ax, ay, bx, by)

        for i, (px, py) in enumerate(self._wp_pixels):
            if i in self._selected:
                order = self._selected.index(i) + 1
                fill = QColor(220, 50, 50)
                centre_label = str(order)
            else:
                fill = QColor(50, 190, 50)
                centre_label = str(i)

            painter.setBrush(fill)
            painter.setPen(QPen(Qt.black, 1))
            painter.drawEllipse(px - R, py - R, R * 2, R * 2)

            f = QFont()
            f.setPointSize(9)
            f.setBold(i in self._selected)
            painter.setFont(f)
            painter.setPen(QPen(Qt.white))
            painter.drawText(px - R, py - R, R * 2, R * 2, Qt.AlignCenter, centre_label)

            if i in self._selected:
                bs = R - 2
                bx2, by2 = px + 2, py - R - bs + 2
                painter.setBrush(QColor(40, 40, 40, 200))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(bx2, by2, bs, bs)
                f2 = QFont()
                f2.setPointSize(6)
                painter.setFont(f2)
                painter.setPen(QPen(QColor(255, 230, 0)))
                painter.drawText(bx2, by2, bs, bs, Qt.AlignCenter, str(i))

        painter.end()
        self.setPixmap(canvas)

    def mousePressEvent(self, event):
        ex, ey = event.x(), event.y()
        R = CIRCLE_RADIUS
        for i, (px, py) in enumerate(self._wp_pixels):
            if (ex - px) ** 2 + (ey - py) ** 2 <= R ** 2:
                if i in self._selected:
                    self._selected.remove(i)
                else:
                    self._selected.append(i)
                self._render()
                self._on_change()
                return

    def selected_indices(self):
        return list(self._selected)


class TspWindow(QWidget):
    # Signal emitted from ROS thread; connected to slot on Qt main thread
    _show_requested = pyqtSignal()
    _map_refresh_requested = pyqtSignal()

    def __init__(self, node: TspGuiNode, map_msg: OccupancyGrid, waypoints):
        super().__init__()
        self.node = node
        self.setWindowTitle("TSP Waypoint Selector")

        self._show_requested.connect(self._on_show_requested)
        self._map_refresh_requested.connect(self._on_map_refresh_requested)

        self._map_msg = map_msg
        self._waypoints = waypoints
        self.map_widget = None
        self.label = QLabel()
        self.label.setWordWrap(True)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._on_clear)
        self.start_btn = QPushButton("Start Tour")
        self.start_btn.clicked.connect(self._on_start)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.start_btn)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)

        self._layout = QVBoxLayout()
        self._layout.addWidget(self.label)
        self._layout.addWidget(self.scroll)
        self._layout.addLayout(btn_row)
        self.setLayout(self._layout)

        self._build_map_widget()

    def _screen_geometry(self):
        screen = QApplication.primaryScreen().availableGeometry()
        win_w = screen.width() // 2
        win_h = screen.height() // 2
        return screen, win_w, win_h

    def _build_map_widget(self):
        """(Re)build the map widget from current node data."""
        map_msg = self.node.map_msg or self._map_msg
        waypoints = self.node.waypoints or self._waypoints
        previous_selection = []
        if self.map_widget is not None:
            previous_selection = self.map_widget.selected_indices()

        _, win_w, win_h = self._screen_geometry()
        map_area_w = win_w - 40
        map_area_h = win_h - 120

        qimage = _occupancy_grid_to_image(map_msg)
        scale = min(map_area_w / max(qimage.width(), 1), map_area_h / max(qimage.height(), 1))
        scaled_w = int(qimage.width() * scale)
        scaled_h = int(qimage.height() * scale)
        base_pixmap = QPixmap.fromImage(qimage).scaled(
            scaled_w, scaled_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        self.map_widget = MapWidget(base_pixmap, waypoints, map_msg.info, scale)
        self.map_widget._selected = [
            index for index in previous_selection if index < len(waypoints)
        ]
        self.map_widget.set_change_callback(self._update_label)
        self.scroll.setMinimumSize(map_area_w, map_area_h)
        self.scroll.setWidget(self.map_widget)
        self.map_widget._render()

        n = len(waypoints)
        self.label.setText(
            f"{n} waypoint{'s' if n != 1 else ''} loaded.  Click to select in tour order, then press Start."
        )

    def request_show(self):
        """Thread-safe: called from ROS thread."""
        self._show_requested.emit()

    def request_map_refresh(self):
        """Thread-safe: called from ROS thread when /map updates."""
        self._map_refresh_requested.emit()

    def _on_show_requested(self):
        """Runs on Qt main thread — rebuild widget so latest data is shown."""
        self._build_map_widget()
        screen, win_w, win_h = self._screen_geometry()
        self.setMinimumSize(win_w, win_h)
        self.show()
        self.resize(win_w, win_h)
        self.move(screen.x() + screen.width() // 4, screen.y() + screen.height() // 4)
        self.raise_()
        self.activateWindow()

    def _on_map_refresh_requested(self):
        """Runs on Qt main thread — redraw with the latest /map message."""
        self._build_map_widget()

    def _update_label(self):
        sel = self.map_widget.selected_indices()
        if sel:
            self.label.setText(
                f"Tour order: {' → '.join(str(s) for s in sel)}   |   Press Start when ready."
            )
        else:
            n = len(self.node.waypoints)
            self.label.setText(
                f"{n} waypoint{'s' if n != 1 else ''} loaded.  Click to select in tour order, then press Start."
            )

    def _on_clear(self):
        if self.map_widget:
            self.map_widget._selected.clear()
            self.map_widget._render()
            self._update_label()

    def _on_start(self):
        if not self.map_widget:
            return
        indices = self.map_widget.selected_indices()
        if not indices:
            self.label.setText("Select at least one waypoint before starting.")
            return
        self.node.publish_tsp(indices)
        self.hide()  # stay alive for next invocation


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_LOCK_PATH = os.path.join(tempfile.gettempdir(), "tsp_gui_single_instance.lock")


def main():
    lock_handle = open(_LOCK_PATH, "w")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("[tsp_gui] Another TSP GUI instance is already running; exiting.", flush=True)
        lock_handle.close()
        return

    parser = argparse.ArgumentParser(description="TSP Waypoint Selector GUI (persistent node)")
    parser.add_argument("--map-yaml", default=None)
    parser.add_argument("--db", default=None)
    known, _ = parser.parse_known_args()

    rclpy.init()
    node = TspGuiNode()

    # Create Qt app first (required before any QWidget)
    app = QApplication(sys.argv)

    # Load initial data synchronously (ros_thread not started yet)
    node.fetch_waypoints(db_fallback=known.db)
    node.wait_for_map(timeout=5.0, map_yaml_fallback=known.map_yaml)

    if node.map_msg is None:
        node.get_logger().warning("No map available — using blank background.")
        dummy = OccupancyGrid()
        dummy.info.width = 400
        dummy.info.height = 300
        dummy.info.resolution = 0.05
        dummy.info.origin.position.x = -10.0
        dummy.info.origin.position.y = -7.5
        dummy.data = [0] * (400 * 300)
        node.map_msg = dummy

    # Create window hidden — shown only when /tsp_gui/show is received
    window = TspWindow(node, node.map_msg, node.waypoints)
    window.hide()

    # Start ROS spin on background thread, then register window
    ros_thread = threading.Thread(target=lambda: rclpy.spin(node), daemon=True)
    ros_thread.start()
    node.set_window(window)

    try:
        app.exec_()
    finally:
        rclpy.shutdown()
        lock_handle.close()


if __name__ == "__main__":
    main()
