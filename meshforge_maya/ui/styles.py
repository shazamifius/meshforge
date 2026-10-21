"""MeshForge Maya - Modern Dark QSS Theme.
Designed to blend seamlessly into Autodesk Maya's native UI aesthetic.
"""

MAYA_DARK_STYLE = """
QWidget {
    background-color: #2b2b2b;
    color: #e0e0e0;
    font-family: "Segoe UI", "Open Sans", Arial, sans-serif;
    font-size: 11px;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QGroupBox {
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
    color: #4a90e2;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    background-color: #2b2b2b;
}

QPushButton {
    background-color: #383838;
    color: #e0e0e0;
    border: 1px solid #4a4a4a;
    border-radius: 3px;
    padding: 5px 12px;
    min-height: 20px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #444444;
    border-color: #4a90e2;
}

QPushButton:pressed {
    background-color: #282828;
}

QPushButton#PrimaryButton {
    background-color: #2b5b88;
    border-color: #4a90e2;
    color: #ffffff;
    font-weight: bold;
    min-height: 28px;
    font-size: 12px;
}

QPushButton#PrimaryButton:hover {
    background-color: #3570a8;
}

QPushButton#DangerButton {
    background-color: #7a2626;
    border-color: #e74c3c;
    color: #ffffff;
}

QPushButton#DangerButton:hover {
    background-color: #933030;
}

QPushButton#SuccessButton {
    background-color: #23653f;
    border-color: #2ecc71;
    color: #ffffff;
}

QPushButton#SuccessButton:hover {
    background-color: #2b7a4d;
}

QComboBox {
    background-color: #333333;
    border: 1px solid #4a4a4a;
    border-radius: 3px;
    padding: 4px 8px;
    color: #e0e0e0;
    min-height: 22px;
}

QComboBox:hover {
    border-color: #4a90e2;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QCheckBox {
    spacing: 6px;
    color: #cccccc;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #555555;
    border-radius: 2px;
    background-color: #262626;
}

QCheckBox::indicator:checked {
    background-color: #4a90e2;
    border-color: #4a90e2;
}

QSlider::groove:horizontal {
    height: 4px;
    background: #3d3d3d;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: #4a90e2;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #e0e0e0;
    border: 1px solid #222222;
    width: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}

QSpinBox, QDoubleSpinBox, QLineEdit {
    background-color: #222222;
    border: 1px solid #444444;
    border-radius: 3px;
    padding: 3px 6px;
    color: #ffffff;
}

QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover {
    border-color: #4a90e2;
}

QFrame#CardBox {
    background-color: #252525;
    border: 1px solid #383838;
    border-radius: 4px;
    padding: 6px;
}

QFrame#AlertBox {
    background-color: #382020;
    border: 1px solid #e74c3c;
    border-radius: 4px;
    padding: 6px;
}

QFrame#InfoBox {
    background-color: #202b38;
    border: 1px solid #4a90e2;
    border-radius: 4px;
    padding: 6px;
}

QLabel#HeaderTitle {
    font-size: 13px;
    font-weight: bold;
    color: #ffffff;
}
"""
