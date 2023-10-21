# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'form.ui'
##
## Created by: Qt User Interface Compiler version 6.5.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QAbstractScrollArea, QApplication, QComboBox,
    QGraphicsView, QGridLayout, QGroupBox, QLabel,
    QLineEdit, QListView, QListWidget, QListWidgetItem,
    QPushButton, QSizePolicy, QTabWidget, QWidget)

class Ui_PPG(object):
    def setupUi(self, PPG):
        if not PPG.objectName():
            PPG.setObjectName(u"PPG")
        PPG.resize(1600, 900)
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(PPG.sizePolicy().hasHeightForWidth())
        PPG.setSizePolicy(sizePolicy)
        self.gridLayout_2 = QGridLayout(PPG)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.groupBox_3 = QGroupBox(PPG)
        self.groupBox_3.setObjectName(u"groupBox_3")
        sizePolicy1 = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.groupBox_3.sizePolicy().hasHeightForWidth())
        self.groupBox_3.setSizePolicy(sizePolicy1)
        font = QFont()
        font.setPointSize(18)
        self.groupBox_3.setFont(font)
        self.gridLayout_8 = QGridLayout(self.groupBox_3)
        self.gridLayout_8.setObjectName(u"gridLayout_8")
        self.groupBox_7 = QGroupBox(self.groupBox_3)
        self.groupBox_7.setObjectName(u"groupBox_7")
        sizePolicy2 = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.groupBox_7.sizePolicy().hasHeightForWidth())
        self.groupBox_7.setSizePolicy(sizePolicy2)
        self.groupBox_7.setFont(font)
        self.gridLayout_7 = QGridLayout(self.groupBox_7)
        self.gridLayout_7.setObjectName(u"gridLayout_7")
        self.pushButton_Event = QPushButton(self.groupBox_7)
        self.pushButton_Event.setObjectName(u"pushButton_Event")
        self.pushButton_Event.setEnabled(False)
        sizePolicy3 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.pushButton_Event.sizePolicy().hasHeightForWidth())
        self.pushButton_Event.setSizePolicy(sizePolicy3)
        self.pushButton_Event.setMaximumSize(QSize(350, 16777215))

        self.gridLayout_7.addWidget(self.pushButton_Event, 3, 0, 1, 1)

        self.pushButton_start_live_acquisition = QPushButton(self.groupBox_7)
        self.pushButton_start_live_acquisition.setObjectName(u"pushButton_start_live_acquisition")
        self.pushButton_start_live_acquisition.setEnabled(False)
        sizePolicy2.setHeightForWidth(self.pushButton_start_live_acquisition.sizePolicy().hasHeightForWidth())
        self.pushButton_start_live_acquisition.setSizePolicy(sizePolicy2)
        self.pushButton_start_live_acquisition.setMaximumSize(QSize(450, 16777215))
        self.pushButton_start_live_acquisition.setFont(font)

        self.gridLayout_7.addWidget(self.pushButton_start_live_acquisition, 1, 0, 1, 2)

        self.pushButton_record_data = QPushButton(self.groupBox_7)
        self.pushButton_record_data.setObjectName(u"pushButton_record_data")
        self.pushButton_record_data.setEnabled(False)
        sizePolicy2.setHeightForWidth(self.pushButton_record_data.sizePolicy().hasHeightForWidth())
        self.pushButton_record_data.setSizePolicy(sizePolicy2)
        self.pushButton_record_data.setMaximumSize(QSize(450, 16777215))
        self.pushButton_record_data.setFont(font)

        self.gridLayout_7.addWidget(self.pushButton_record_data, 2, 0, 1, 2)

        self.comboBox_event = QComboBox(self.groupBox_7)
        self.comboBox_event.setObjectName(u"comboBox_event")
        sizePolicy2.setHeightForWidth(self.comboBox_event.sizePolicy().hasHeightForWidth())
        self.comboBox_event.setSizePolicy(sizePolicy2)

        self.gridLayout_7.addWidget(self.comboBox_event, 3, 1, 1, 1)


        self.gridLayout_8.addWidget(self.groupBox_7, 4, 1, 1, 1)

        self.groupBox_4 = QGroupBox(self.groupBox_3)
        self.groupBox_4.setObjectName(u"groupBox_4")
        sizePolicy2.setHeightForWidth(self.groupBox_4.sizePolicy().hasHeightForWidth())
        self.groupBox_4.setSizePolicy(sizePolicy2)
        self.groupBox_4.setFont(font)
        self.gridLayout_5 = QGridLayout(self.groupBox_4)
        self.gridLayout_5.setObjectName(u"gridLayout_5")
        self.lineEdit_PID = QLineEdit(self.groupBox_4)
        self.lineEdit_PID.setObjectName(u"lineEdit_PID")
        sizePolicy2.setHeightForWidth(self.lineEdit_PID.sizePolicy().hasHeightForWidth())
        self.lineEdit_PID.setSizePolicy(sizePolicy2)
        self.lineEdit_PID.setMaximumSize(QSize(250, 16777215))

        self.gridLayout_5.addWidget(self.lineEdit_PID, 2, 1, 1, 1)

        self.label_7 = QLabel(self.groupBox_4)
        self.label_7.setObjectName(u"label_7")
        sizePolicy2.setHeightForWidth(self.label_7.sizePolicy().hasHeightForWidth())
        self.label_7.setSizePolicy(sizePolicy2)
        self.label_7.setMaximumSize(QSize(200, 16777215))

        self.gridLayout_5.addWidget(self.label_7, 2, 0, 1, 1)

        self.pushButton_exp_params = QPushButton(self.groupBox_4)
        self.pushButton_exp_params.setObjectName(u"pushButton_exp_params")
        sizePolicy2.setHeightForWidth(self.pushButton_exp_params.sizePolicy().hasHeightForWidth())
        self.pushButton_exp_params.setSizePolicy(sizePolicy2)
        self.pushButton_exp_params.setMaximumSize(QSize(200, 16777215))

        self.gridLayout_5.addWidget(self.pushButton_exp_params, 0, 0, 1, 1)

        self.listWidget_expConditions = QListWidget(self.groupBox_4)
        self.listWidget_expConditions.setObjectName(u"listWidget_expConditions")
        self.listWidget_expConditions.setEnabled(True)
        sizePolicy2.setHeightForWidth(self.listWidget_expConditions.sizePolicy().hasHeightForWidth())
        self.listWidget_expConditions.setSizePolicy(sizePolicy2)
        self.listWidget_expConditions.setMaximumSize(QSize(250, 16777215))
        font1 = QFont()
        font1.setPointSize(18)
        font1.setBold(False)
        self.listWidget_expConditions.setFont(font1)
        self.listWidget_expConditions.setMouseTracking(True)
        self.listWidget_expConditions.setEditTriggers(QAbstractItemView.CurrentChanged|QAbstractItemView.DoubleClicked|QAbstractItemView.EditKeyPressed|QAbstractItemView.SelectedClicked)
        self.listWidget_expConditions.setAlternatingRowColors(True)
        self.listWidget_expConditions.setSpacing(1)
        self.listWidget_expConditions.setViewMode(QListView.ListMode)
        self.listWidget_expConditions.setSelectionRectVisible(False)
        self.listWidget_expConditions.setSortingEnabled(False)

        self.gridLayout_5.addWidget(self.listWidget_expConditions, 6, 1, 1, 1)

        self.label_3 = QLabel(self.groupBox_4)
        self.label_3.setObjectName(u"label_3")
        sizePolicy2.setHeightForWidth(self.label_3.sizePolicy().hasHeightForWidth())
        self.label_3.setSizePolicy(sizePolicy2)
        self.label_3.setMaximumSize(QSize(200, 16777215))
        self.label_3.setFont(font)

        self.gridLayout_5.addWidget(self.label_3, 6, 0, 1, 1)

        self.label_params_file = QLabel(self.groupBox_4)
        self.label_params_file.setObjectName(u"label_params_file")
        self.label_params_file.setEnabled(False)
        sizePolicy2.setHeightForWidth(self.label_params_file.sizePolicy().hasHeightForWidth())
        self.label_params_file.setSizePolicy(sizePolicy2)
        self.label_params_file.setMaximumSize(QSize(250, 16777215))

        self.gridLayout_5.addWidget(self.label_params_file, 0, 1, 1, 1)

        self.label_2 = QLabel(self.groupBox_4)
        self.label_2.setObjectName(u"label_2")
        sizePolicy2.setHeightForWidth(self.label_2.sizePolicy().hasHeightForWidth())
        self.label_2.setSizePolicy(sizePolicy2)
        self.label_2.setMaximumSize(QSize(200, 16777215))
        self.label_2.setFont(font)

        self.gridLayout_5.addWidget(self.label_2, 1, 0, 1, 1)

        self.label_study_name = QLabel(self.groupBox_4)
        self.label_study_name.setObjectName(u"label_study_name")
        sizePolicy2.setHeightForWidth(self.label_study_name.sizePolicy().hasHeightForWidth())
        self.label_study_name.setSizePolicy(sizePolicy2)
        self.label_study_name.setMaximumSize(QSize(250, 16777215))

        self.gridLayout_5.addWidget(self.label_study_name, 1, 1, 1, 1)


        self.gridLayout_8.addWidget(self.groupBox_4, 1, 1, 1, 1)

        self.groupBox_6 = QGroupBox(self.groupBox_3)
        self.groupBox_6.setObjectName(u"groupBox_6")
        sizePolicy2.setHeightForWidth(self.groupBox_6.sizePolicy().hasHeightForWidth())
        self.groupBox_6.setSizePolicy(sizePolicy2)
        self.groupBox_6.setFont(font)
        self.gridLayout_6 = QGridLayout(self.groupBox_6)
        self.gridLayout_6.setObjectName(u"gridLayout_6")
        self.label_10 = QLabel(self.groupBox_6)
        self.label_10.setObjectName(u"label_10")
        sizePolicy2.setHeightForWidth(self.label_10.sizePolicy().hasHeightForWidth())
        self.label_10.setSizePolicy(sizePolicy2)
        self.label_10.setMaximumSize(QSize(140, 16777215))
        self.label_10.setFont(font)

        self.gridLayout_6.addWidget(self.label_10, 1, 0, 1, 1)

        self.comboBox_comport = QComboBox(self.groupBox_6)
        self.comboBox_comport.setObjectName(u"comboBox_comport")
        sizePolicy2.setHeightForWidth(self.comboBox_comport.sizePolicy().hasHeightForWidth())
        self.comboBox_comport.setSizePolicy(sizePolicy2)
        self.comboBox_comport.setMaximumSize(QSize(200, 16777215))
        self.comboBox_comport.setFont(font)

        self.gridLayout_6.addWidget(self.comboBox_comport, 1, 1, 1, 1)

        self.pushButton_connect = QPushButton(self.groupBox_6)
        self.pushButton_connect.setObjectName(u"pushButton_connect")
        self.pushButton_connect.setEnabled(False)
        sizePolicy2.setHeightForWidth(self.pushButton_connect.sizePolicy().hasHeightForWidth())
        self.pushButton_connect.setSizePolicy(sizePolicy2)
        self.pushButton_connect.setMaximumSize(QSize(150, 16777215))
        self.pushButton_connect.setFont(font)

        self.gridLayout_6.addWidget(self.pushButton_connect, 1, 2, 1, 1)

        self.pushButton_sync = QPushButton(self.groupBox_6)
        self.pushButton_sync.setObjectName(u"pushButton_sync")
        self.pushButton_sync.setEnabled(False)
        sizePolicy2.setHeightForWidth(self.pushButton_sync.sizePolicy().hasHeightForWidth())
        self.pushButton_sync.setSizePolicy(sizePolicy2)
        self.pushButton_sync.setMaximumSize(QSize(350, 16777215))

        self.gridLayout_6.addWidget(self.pushButton_sync, 3, 1, 1, 2)

        self.label_sync = QLabel(self.groupBox_6)
        self.label_sync.setObjectName(u"label_sync")
        self.label_sync.setEnabled(False)
        sizePolicy2.setHeightForWidth(self.label_sync.sizePolicy().hasHeightForWidth())
        self.label_sync.setSizePolicy(sizePolicy2)
        self.label_sync.setMaximumSize(QSize(160, 16777215))

        self.gridLayout_6.addWidget(self.label_sync, 3, 0, 1, 1)


        self.gridLayout_8.addWidget(self.groupBox_6, 0, 1, 1, 1)


        self.gridLayout_2.addWidget(self.groupBox_3, 2, 0, 2, 1)

        self.groupBox_5 = QGroupBox(PPG)
        self.groupBox_5.setObjectName(u"groupBox_5")
        sizePolicy4 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.groupBox_5.sizePolicy().hasHeightForWidth())
        self.groupBox_5.setSizePolicy(sizePolicy4)
        self.groupBox_5.setMinimumSize(QSize(0, 60))
        self.groupBox_5.setMaximumSize(QSize(16777215, 80))
        font2 = QFont()
        font2.setPointSize(16)
        self.groupBox_5.setFont(font2)
        self.gridLayout_4 = QGridLayout(self.groupBox_5)
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.label_status = QLabel(self.groupBox_5)
        self.label_status.setObjectName(u"label_status")
        sizePolicy5 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sizePolicy5.setHorizontalStretch(0)
        sizePolicy5.setVerticalStretch(0)
        sizePolicy5.setHeightForWidth(self.label_status.sizePolicy().hasHeightForWidth())
        self.label_status.setSizePolicy(sizePolicy5)
        self.label_status.setMaximumSize(QSize(16777215, 75))
        self.label_status.setFont(font2)

        self.gridLayout_4.addWidget(self.label_status, 1, 0, 1, 1)


        self.gridLayout_2.addWidget(self.groupBox_5, 5, 0, 1, 3)

        self.label = QLabel(PPG)
        self.label.setObjectName(u"label")
        sizePolicy5.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy5)
        self.label.setMinimumSize(QSize(0, 80))
        self.label.setFont(font)
        self.label.setScaledContents(True)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setMargin(-1)

        self.gridLayout_2.addWidget(self.label, 0, 0, 1, 3)

        self.tabWidget = QTabWidget(PPG)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tabWidget.setFont(font2)
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.gridLayout = QGridLayout(self.tab)
        self.gridLayout.setObjectName(u"gridLayout")
        self.graphicsView = QGraphicsView(self.tab)
        self.graphicsView.setObjectName(u"graphicsView")
        sizePolicy6 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sizePolicy6.setHorizontalStretch(0)
        sizePolicy6.setVerticalStretch(0)
        sizePolicy6.setHeightForWidth(self.graphicsView.sizePolicy().hasHeightForWidth())
        self.graphicsView.setSizePolicy(sizePolicy6)
        self.graphicsView.setFont(font)
        self.graphicsView.setAcceptDrops(False)
        self.graphicsView.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.graphicsView.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.graphicsView.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.graphicsView.setInteractive(False)

        self.gridLayout.addWidget(self.graphicsView, 0, 0, 1, 1)

        self.label_sq_legend = QLabel(self.tab)
        self.label_sq_legend.setObjectName(u"label_sq_legend")
        sizePolicy4.setHeightForWidth(self.label_sq_legend.sizePolicy().hasHeightForWidth())
        self.label_sq_legend.setSizePolicy(sizePolicy4)
        self.label_sq_legend.setMaximumSize(QSize(16777215, 40))
        self.label_sq_legend.setScaledContents(True)

        self.gridLayout.addWidget(self.label_sq_legend, 1, 0, 1, 1)

        self.tabWidget.addTab(self.tab, "")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.gridLayout_3 = QGridLayout(self.tab_2)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.label_biofeedback = QLabel(self.tab_2)
        self.label_biofeedback.setObjectName(u"label_biofeedback")
        self.label_biofeedback.setScaledContents(True)

        self.gridLayout_3.addWidget(self.label_biofeedback, 0, 1, 1, 1)

        self.label_palette = QLabel(self.tab_2)
        self.label_palette.setObjectName(u"label_palette")
        sizePolicy2.setHeightForWidth(self.label_palette.sizePolicy().hasHeightForWidth())
        self.label_palette.setSizePolicy(sizePolicy2)
        self.label_palette.setMaximumSize(QSize(50, 16777215))

        self.gridLayout_3.addWidget(self.label_palette, 0, 0, 1, 1)

        self.tabWidget.addTab(self.tab_2, "")

        self.gridLayout_2.addWidget(self.tabWidget, 2, 1, 1, 1)


        self.retranslateUi(PPG)

        self.listWidget_expConditions.setCurrentRow(-1)
        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(PPG)
    # setupUi

    def retranslateUi(self, PPG):
        PPG.setWindowTitle(QCoreApplication.translate("PPG", u"PPG", None))
        self.groupBox_3.setTitle(QCoreApplication.translate("PPG", u"Experiment Controls", None))
        self.groupBox_7.setTitle(QCoreApplication.translate("PPG", u"Running Experiment", None))
        self.pushButton_Event.setText(QCoreApplication.translate("PPG", u"Start Marking", None))
        self.pushButton_start_live_acquisition.setText(QCoreApplication.translate("PPG", u"Start Live Acquisition", None))
        self.pushButton_record_data.setText(QCoreApplication.translate("PPG", u"Record Data", None))
        self.groupBox_4.setTitle(QCoreApplication.translate("PPG", u"Experiment Specification", None))
        self.label_7.setText(QCoreApplication.translate("PPG", u"Participant ID", None))
        self.pushButton_exp_params.setText(QCoreApplication.translate("PPG", u"Load \n"
"Experiment", None))
        self.label_3.setText(QCoreApplication.translate("PPG", u"Experimental \n"
"Conditions", None))
        self.label_params_file.setText(QCoreApplication.translate("PPG", u"filepath", None))
        self.label_2.setText(QCoreApplication.translate("PPG", u"Study Name", None))
        self.label_study_name.setText("")
        self.groupBox_6.setTitle(QCoreApplication.translate("PPG", u"Device Setup", None))
        self.label_10.setText(QCoreApplication.translate("PPG", u"Com Port", None))
        self.pushButton_connect.setText(QCoreApplication.translate("PPG", u"Connect", None))
        self.pushButton_sync.setText("")
        self.label_sync.setText(QCoreApplication.translate("PPG", u"External Sync", None))
        self.groupBox_5.setTitle(QCoreApplication.translate("PPG", u"Info", None))
        self.label_status.setText("")
        self.label.setText("")
        self.label_sq_legend.setText("")
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab), QCoreApplication.translate("PPG", u"Real-Time Plotting of Signals", None))
        self.label_biofeedback.setText("")
        self.label_palette.setText("")
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_2), QCoreApplication.translate("PPG", u"Visual Bio-Feedback", None))
    # retranslateUi

