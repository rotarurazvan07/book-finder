import sys

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QTableWidgetItem

import utils

LABEL_CHOOSE_PAGES_TEXT_TEMPLATE = "Choose number of pages to search (1 - %s)"


class Ui_MainWindow(object):
    def __init__(self, app):
        self.exportButton = None
        self.booklistTable = None
        self.progressBar = None
        self.searchButton = None
        self.breakConditionSpinBox = None
        self.labelChoosePages = None
        self.categoryBox = None
        self.centralwidget = None
        self.labelChooseCategory = None
        self.bookstoreBox = None
        self.labelChooseBookstore = None
        self.app = app

    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1059, 594)

        self.labelChooseBookstore = QtWidgets.QLabel(MainWindow)
        self.labelChooseBookstore.setGeometry(QtCore.QRect(30, 15, 121, 21))
        self.labelChooseBookstore.setAutoFillBackground(True)
        self.labelChooseBookstore.setObjectName("labelChooseBookstore")
        self.labelChooseBookstore.setText("Choose the bookstore")

        self.bookstoreBox = QtWidgets.QComboBox(MainWindow)
        self.bookstoreBox.setGeometry(QtCore.QRect(30, 40, 221, 21))
        self.bookstoreBox.setEditable(True)
        self.bookstoreBox.setPlaceholderText("")
        self.bookstoreBox.setObjectName("bookstoreBox")
        self.bookstoreBox.currentIndexChanged.connect(self.app.updateCategories)

        self.labelChooseCategory = QtWidgets.QLabel(MainWindow)
        self.labelChooseCategory.setGeometry(QtCore.QRect(30, 76, 121, 20))
        self.labelChooseCategory.setAutoFillBackground(True)
        self.labelChooseCategory.setObjectName("labelChooseCategory")
        self.labelChooseCategory.setText("Choose the category")

        self.categoryBox = QtWidgets.QComboBox(MainWindow)
        self.categoryBox.setGeometry(QtCore.QRect(30, 100, 221, 21))
        self.categoryBox.setEditable(True)
        self.categoryBox.setPlaceholderText("")
        self.categoryBox.setObjectName("categoryBox")
        self.categoryBox.currentIndexChanged.connect(self.app.updatePagesRange)

        self.labelChoosePages = QtWidgets.QLabel(MainWindow)
        self.labelChoosePages.setGeometry(QtCore.QRect(30, 135, 221, 21))
        self.labelChoosePages.setAutoFillBackground(True)
        self.labelChoosePages.setObjectName("labelChoosePages")

        self.breakConditionSpinBox = QtWidgets.QSpinBox(MainWindow)
        self.breakConditionSpinBox.setGeometry(QtCore.QRect(30, 160, 61, 21))
        self.breakConditionSpinBox.setObjectName("breakConditionSpinBox")

        self.progressBar = QtWidgets.QProgressBar(MainWindow)
        self.progressBar.setGeometry(QtCore.QRect(30, 200, 231, 21))
        self.progressBar.setValue(0)
        self.progressBar.setObjectName("progressBar")

        self.searchButton = QtWidgets.QPushButton(MainWindow)
        self.searchButton.setGeometry(QtCore.QRect(30, 240, 91, 31))
        self.searchButton.setObjectName("searchButton")
        self.searchButton.clicked.connect(self.app.getBooklist)
        self.searchButton.setText("Search")

        self.booklistTable = QtWidgets.QTableWidget(MainWindow)
        self.booklistTable.setGeometry(QtCore.QRect(270, 10, 771, 571))
        self.booklistTable.setAutoScroll(False)
        self.booklistTable.setShowGrid(True)
        self.booklistTable.setColumnCount(5)
        self.booklistTable.setObjectName("booklistTable")
        self.booklistTable.setRowCount(0)
        self.booklistTable.setSortingEnabled(False)
        self.booklistTable.setHorizontalHeaderLabels(['Author', 'Title', 'Rating', 'Price', 'URL'])
        self.booklistTable.setColumnWidth(0, 200)
        self.booklistTable.setColumnWidth(1, 200)
        self.booklistTable.setColumnWidth(2, 50)
        self.booklistTable.setColumnWidth(3, 50)
        self.booklistTable.setColumnWidth(4, 250)

        self.exportButton = QtWidgets.QPushButton(MainWindow)
        self.exportButton.setGeometry(QtCore.QRect(140, 240, 91, 31))
        self.exportButton.setObjectName("exportButton")
        self.exportButton.setText("Export")
        self.exportButton.setEnabled(False)
        self.exportButton.clicked.connect(self.app.exportBooklist)

        MainWindow.setCentralWidget(self.centralwidget)


class MainWindowApp:
    def __init__(self, bookstores):
        self.app = QtWidgets.QApplication([])
        self.MainWindow = QtWidgets.QMainWindow()
        self.ui = Ui_MainWindow(self)
        self.ui.setupUi(self.MainWindow)
        self.bookstores = bookstores

        self.populateComboBox([bookstore.name for bookstore in self.bookstores], "bookstores")

    def start(self):
        self.MainWindow.show()
        sys.exit(self.app.exec_())

    def _getSelectedBookstore(self):
        return self.bookstores[self.ui.bookstoreBox.currentIndex()]

    def getBooklist(self):
        bookstore = self._getSelectedBookstore()
        category = self.ui.categoryBox.currentText()
        break_page = self.ui.breakConditionSpinBox.value()

        search_url = bookstore.getSearchUrl(category)

        self.ui.exportButton.setEnabled(False)

        self.ui.booklistTable.clearContents()
        self.ui.booklistTable.setRowCount(0)

        self.ui.progressBar.setValue(0)
        self.ui.progressBar.setMaximum(break_page)

        booklist_worker = GetBooklistWorker(self.MainWindow, bookstore, search_url, break_page)
        booklist_worker.progress_updated.connect(self.updateProgress)
        booklist_worker.finished.connect(self.onGetBooklistFinished)
        booklist_worker.start()

    def onGetBooklistFinished(self):
        self.ui.progressBar.setValue(self.ui.progressBar.maximum())
        self.ui.exportButton.setEnabled(True)

    def updateProgress(self):
        bookstore = self._getSelectedBookstore()

        self.ui.progressBar.setValue(bookstore.current_page)

        data = [[book.author, book.title, book.rating, book.price, book.url] for book in bookstore.booklist]
        data = sorted(data, key=lambda x: x[2], reverse=True)

        self.ui.booklistTable.clearContents()
        self.ui.booklistTable.setRowCount(len(data))
        for i in range(len(data)):
            for j in range(len(data[i])):
                item = QTableWidgetItem()
                if j == 2:
                    item.setData(QtCore.Qt.DisplayRole, int(data[i][j]))
                else:
                    item.setData(QtCore.Qt.DisplayRole, str(data[i][j]))
                self.ui.booklistTable.setItem(i, j, item)

    def updateCategories(self):
        bookstore = self._getSelectedBookstore()
        self.populateComboBox(list(bookstore.getCategoryNames()), "categories")

    def updatePagesRange(self):
        bookstore = self._getSelectedBookstore()
        category_url = bookstore.getSearchUrl(self.ui.categoryBox.currentText())
        max_pages = bookstore.getMaxPages(category_url)

        self.ui.breakConditionSpinBox.setRange(1, max_pages)
        self.ui.labelChoosePages.setText(LABEL_CHOOSE_PAGES_TEXT_TEMPLATE % max_pages)

    def populateComboBox(self, elements, combo):
        if combo == "categories":
            self.ui.categoryBox.currentIndexChanged.disconnect(self.updatePagesRange)
            self.ui.categoryBox.clear()
            for elem in elements:
                self.ui.categoryBox.addItem(elem)
            self.ui.categoryBox.currentIndexChanged.connect(self.updatePagesRange)
            self.ui.categoryBox.setCurrentIndex(1)
            self.ui.categoryBox.setCurrentIndex(0)
        elif combo == "bookstores":
            for elem in elements:
                self.ui.bookstoreBox.addItem(elem)

    def exportBooklist(self):
        bookstore = self._getSelectedBookstore()
        utils.exportBooks(bookstore.booklist, bookstore.name)


class GetBooklistWorker(QThread):
    finished = pyqtSignal()
    progress_updated = pyqtSignal()

    def __init__(self, parent, bookstore, search_url, break_page):
        super().__init__(parent)
        self.bookstore = bookstore
        self.search_url = search_url
        self.break_page = break_page

    def run(self):
        update_progress_worker = self.UpdateProgressWorker(self)
        update_progress_worker.progress_updated.connect(self.update_progress)
        update_progress_worker.start()
        self.bookstore.getBookList(self.search_url, self.break_page)
        update_progress_worker.stop()
        update_progress_worker.wait()
        self.finished.emit()

    def update_progress(self):
        self.progress_updated.emit()

    class UpdateProgressWorker(QThread):
        progress_updated = pyqtSignal()
        finished = pyqtSignal()

        def __init__(self, parent):
            super().__init__(parent)
            self._is_running = True

        def run(self):
            while True:
                if self._is_running is False:
                    return
                self.msleep(5000)
                self.progress_updated.emit()

        def stop(self):
            self._is_running = False
