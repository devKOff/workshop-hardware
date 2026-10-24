"""Base class for application pages: large heading, spacious content area."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

class PageBase(QWidget):
    """Every page shares a large heading, subheading, and content area."""

    def __init__(self, heading: str, subheading: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._heading = heading
        self._subheading = subheading
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(0)

        heading = QLabel(self._heading)
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)

        sub = QLabel(self._subheading)
        sub.setObjectName("pageSubheading")
        layout.addWidget(sub)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(14)
        layout.addWidget(self.content, stretch=1)

        # Subclasses populate their content here.
        self._populate_content()

    def _populate_content(self) -> None:
        """Override in subclasses to add page-specific widgets."""
        pass

    def add_widget(self, widget) -> None:
        self.content_layout.addWidget(widget)

    def add_stretch(self) -> None:
        self.content_layout.addStretch()

    def add_layout(self, layout) -> None:
        wrapper = QWidget()
        wrapper.setLayout(layout)
        self.content_layout.addWidget(wrapper)
