# Copyright Bunting Labs, Inc. 2024

from PyQt5.QtWidgets import (
    QDockWidget, QStackedWidget, QWidget, QLineEdit, QPushButton, QHBoxLayout,
    QVBoxLayout, QScrollArea, QListWidget, QFrame, QListWidgetItem, QLabel
)
from PyQt5.QtCore import Qt
from qgis.core import QgsVectorLayer, QgsRasterLayer, QgsProject
from PyQt5.QtGui import QIcon
from qgis.core import QgsIconUtils

from typing import Callable
import os
from .kue_find import KueFind

class KueSidebar(QDockWidget):
    def __init__(self, iface, messageSent: Callable, kue_find: KueFind):
        super().__init__("Kue", iface.mainWindow())

        # Properties
        self.iface = iface
        self.messageSent = messageSent
        self.kue_find = kue_find
        # The parent widget is either kue or auth
        self.parent_widget = QStackedWidget()

        # 1. Build the textbox and enter button widget
        self.message_bar_widget = QWidget()

        self.textbox = QLineEdit()
        self.textbox.returnPressed.connect(self.onEnterClicked)
        self.textbox.textChanged.connect(self.onTextUpdate)

        def handleKeyPress(e):
            if e.key() == Qt.Key_Up:
                user_messages = [msg for msg in [] if msg['role'] == 'user']
                if user_messages:
                    self.textbox.setText(user_messages[-1]['msg'])
            else:
                QLineEdit.keyPressEvent(self.textbox, e)
        self.textbox.keyPressEvent = handleKeyPress

        self.enter_button = QPushButton("Enter")
        self.enter_button.setFixedSize(50, 20)
        self.enter_button.clicked.connect(self.onEnterClicked)

        # Chatbox and button at bottom
        self.h_layout = QHBoxLayout()
        self.h_layout.addWidget(self.textbox)
        self.h_layout.addWidget(self.enter_button)
        self.message_bar_widget.setLayout(self.h_layout)

        # 2. Build the parent for both kue and find
        self.above_mb_widget = QStackedWidget()

        # Build kue widget
        self.kue_widget = QWidget()

        self.chat_display = QListWidget()
        self.chat_display.setWordWrap(True)
        self.chat_display.setFrameShape(QFrame.NoFrame)
        self.chat_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_display.setTextElideMode(Qt.ElideNone)

        self.chat_delegate = KueChatDelegate()
        self.chat_delegate.button_clicked = self.onChatButtonClicked
        self.chat_display.setItemDelegate(self.chat_delegate)

        self.scroll_area = QScrollArea()
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.chat_display)

        self.kue_layout = QVBoxLayout()
        self.kue_layout.addWidget(QLabel("Kue chat"))
        self.kue_layout.addWidget(self.scroll_area)
        self.kue_widget.setLayout(self.kue_layout)

        self.find_widget = QWidget()
        self.find_layout = QVBoxLayout()
        self.find_layout.addWidget(QLabel("Find"))

        self.find_results = QListWidget()
        self.find_results.setWordWrap(True)
        self.find_results.setFrameShape(QFrame.NoFrame)
        self.find_results.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.find_results.setTextElideMode(Qt.ElideNone)
        # Handle opening a file
        # self.find_results.itemDoubleClicked.connect(self.onFindResultOpened)
        # delegation
        delegate = KueFileResult()
        delegate.double_clicked = self.onFindResultOpened
        self.find_results.setItemDelegate(delegate)

        self.find_layout.addWidget(self.find_results)
        self.find_widget.setLayout(self.find_layout)

        self.above_mb_widget.addWidget(self.kue_widget)
        self.above_mb_widget.addWidget(self.find_widget)
        self.above_mb_widget.setCurrentIndex(0)

        # Create a layout for kue (kue chat + find)
        self.kue_layout = QVBoxLayout()
        self.kue_layout.addWidget(self.above_mb_widget)
        self.kue_layout.addWidget(self.message_bar_widget)

        # Add message bar widget to parent widget
        self.kue_widget = QWidget()
        self.kue_widget.setLayout(self.kue_layout)
        self.parent_widget.addWidget(self.kue_widget)

        self.setWidget(self.parent_widget)

    def addMessage(self, msg):
        item = QListWidgetItem()
        # Store full message data in UserRole
        item.setData(Qt.UserRole, msg)
        self.chat_display.addItem(item)

    def onChatButtonClicked(self, msg):
        # Handle button click
        from console import console
        from PyQt5.QtWidgets import QApplication

        self.iface.actionShowPythonDialog().trigger()
        console._console.console.toggleEditor(True)

        QApplication.clipboard().setText(msg['msg'])
        console._console.console.pasteEditor()

    def onEnterClicked(self):
        text = self.textbox.text()
        history = [self.chat_display.item(i).text() for i in range(self.chat_display.count())]
        self.messageSent(text, history)
        self.textbox.clear()

    def onFindResultOpened(self, path: str):
        if path.endswith('.shp'):
            vlayer = QgsVectorLayer(path, os.path.basename(path), 'ogr')
            QgsProject.instance().addMapLayer(vlayer)
        elif path.endswith('.tif'):
            rlayer = QgsRasterLayer(path, os.path.basename(path))
            QgsProject.instance().addMapLayer(rlayer)

    def onTextUpdate(self, text):
        if text.startswith("/find "):
            self.above_mb_widget.setCurrentIndex(1)

            query = text[6:]
            self.find_results.clear()

            # Search
            results = self.kue_find.search(query)
            for (path, atime, file_type, geom_type, location) in results:
                item = QListWidgetItem()
                item.setData(Qt.UserRole, {
                    "path": path.replace(os.path.expanduser("~"), "~"),
                    "atime": atime,
                    "location": location
                })
                if file_type == 'vector':
                    if geom_type == 'Point':
                        item.setIcon(QgsIconUtils.iconPoint())
                    elif geom_type == 'LineString':
                        item.setIcon(QgsIconUtils.iconLine())
                    else:
                        item.setIcon(QgsIconUtils.iconPolygon())
                else:
                    item.setIcon(QgsIconUtils.iconRaster())
                self.find_results.addItem(item)
        else:
            self.above_mb_widget.setCurrentIndex(0)

from PyQt5.QtWidgets import QAbstractItemDelegate
from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QStyle

class KueFileResult(QAbstractItemDelegate):
    def __init__(self, double_clicked=None):
        super().__init__()
        self.double_clicked = double_clicked  # Add callback property

    def editorEvent(self, event, model, option, index):
        if event.type() == event.MouseButtonDblClick and self.double_clicked:
            path = index.data(Qt.UserRole)["path"]
            path = path.replace("~", os.path.expanduser("~"))
            self.double_clicked(path)
            return True
        return False

    def paint(self, painter, option, index):
        # Draw background if selected
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        # Draw bottom line
        painter.setPen(option.palette.dark().color())
        painter.drawLine(
            option.rect.left(),
            option.rect.bottom(),
            option.rect.right(),
            option.rect.bottom()
        )

        # Text color depends on select state
        if option.state & QStyle.State_Selected:
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())

        # Get the icon, draw on top of bg
        icon = index.data(Qt.DecorationRole)
        if icon:
            icon_rect = option.rect.adjusted(4, 4, -option.rect.width() + 24, -4)
            icon.paint(painter, icon_rect)
            
        path = index.data(Qt.UserRole)["path"]
        filename = os.path.basename(path)
        dirname = os.path.dirname(path)

        atime = index.data(Qt.UserRole)["atime"]
        location = index.data(Qt.UserRole)["location"]

        # Draw filename on first line with offset for icon
        font = painter.font()
        font.setBold(False)
        painter.setFont(font)
        text_rect = option.rect.adjusted(28, 4, -4, -int(option.rect.height()/2))
        painter.drawText(
            text_rect,
            Qt.AlignLeft | Qt.AlignVCenter,
            f"{dirname} (opened {atime})"
        )

        # Draw dirname on second line
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            option.rect.adjusted(28, int(option.rect.height()/2), -4, -4),
            Qt.AlignLeft | Qt.AlignVCenter,
            filename
        )
        # Location is lighter gray
        if option.state & QStyle.State_Selected:
            painter.setPen(option.palette.highlightedText().color().lighter())
        else:
            painter.setPen(option.palette.text().color().lighter())

        painter.drawText(
            option.rect.adjusted(28, int(option.rect.height()/2), -4, -4),
            Qt.AlignRight | Qt.AlignVCenter,
            location
        )

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 40)

from PyQt5.QtWidgets import QStyledItemDelegate, QStyle
from PyQt5.QtCore import QSize, QRect
from PyQt5.QtGui import QColor
class KueChatDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.button_clicked = None  # Callback for button clicks

    def paint(self, painter, option, index):
        # Draw selection background if selected
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        msg = index.data(Qt.UserRole)
        if not msg:
            return

        # Draw message text
        text_color = (QColor(255, 0, 0) if msg['role'] == 'error'
                     else option.palette.text().color() if msg['role'] == 'system'
                     else option.palette.text().color())
        painter.setPen(text_color)

        text_rect = option.rect.adjusted(8, 4, -8, -4)
        if msg.get('has_button'):
            text_rect.setRight(text_rect.right() - 70)  # Make room for button

            # Draw button - align to top right
            button_rect = QRect(text_rect.right() + 4, text_rect.top(), 60, 24)
            painter.drawRect(button_rect)
            painter.drawText(button_rect, Qt.AlignCenter, "Run Code")

        # Use drawText with TextWordWrap flag for multiline support
        alignment = Qt.AlignRight if msg['role'] == 'user' else Qt.AlignLeft
        painter.drawText(text_rect, alignment | Qt.AlignVCenter | Qt.TextWordWrap, msg['msg'])

    def editorEvent(self, event, model, option, index):
        if event.type() == event.MouseButtonPress:
            msg = index.data(Qt.UserRole)
            if msg.get('has_button'):
                button_rect = QRect(option.rect.right() - 54, option.rect.top() + 4, 50, 24)
                if button_rect.contains(event.pos()):
                    if self.button_clicked:
                        self.button_clicked(msg)
                    return True
        return False

    def sizeHint(self, option, index):
        msg = index.data(Qt.UserRole)
        if not msg:
            return QSize(option.rect.width(), 32)

        # Calculate height needed for wrapped text
        text_rect = option.rect.adjusted(8, 4, -8, -4)
        if msg.get('has_button'):
            text_rect.setRight(text_rect.right() - 60)  # Account for button width

        metrics = option.fontMetrics
        text_height = metrics.boundingRect(text_rect, Qt.TextWordWrap, msg['msg']).height()

        # Return max of text height or minimum height
        return QSize(option.rect.width(), max(text_height + 8, 32))
