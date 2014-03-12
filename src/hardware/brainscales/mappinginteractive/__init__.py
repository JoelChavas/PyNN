"""

 several widgets that display information
 during the interactive mapping process

"""
import sys
import os
import subprocess
import numpy

from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4 import uic

import pymongo
import json as json
import pprint as pprint

from treeHMF import *  # costumized tree view
from itemsHMF import *  # costumized graphic view items
from viewsHMF import * # costumized graphic views

import mappingutilities
import statisticplot

MAPPINGINTERACTIVEPATH = os.environ['SYMAP2IC_PATH']+'/components/pynnhw/src/hardware/brainscales/mappinginteractive/'
JSONPATH = os.environ['SYMAP2IC_PATH']+'/components/mappingtool/script/stage2/JSON/default'

DATABASEIP = 'localhost'
DATABASEPORT = 27017
INTERACTIVEDBPPORT = 12345
INTERACTIVEDBPATH = 'mongodb'
INTERACTIVEDBDATA = INTERACTIVEDBPATH + '/data/db'
INTERACTIVEDBLOGS = INTERACTIVEDBPATH + '/log'
INTERACTIVEDBLOGFILE = INTERACTIVEDBLOGS + '/mongod.log'

WAFER_COUNT_HMF = 6

STEP_PREPROCESSING = 0
STEP_POSTPROCESSING = 1

STATISTICSFOLDER = 'mapping_statistics/'

# TODO -- ME: provide an Qt application with connect to database dialogue, help etc. 

"""

 widget providing several pre-post-processing statistics,
 an HMF overview and an abstract HICANN view

"""
class InteractiveMapping(QtGui.QWidget):

    def __init__(self, statistics,
                 mappingstep=0,experimentname='no name',
                 mappinglog='no name', ignoredb=False,
                 dbip=DATABASEIP,dbport=DATABASEPORT,
                 jsons=JSONPATH,parent=None) :
        '''
        @param statistics helper to retrieve mapping statistics
        @param mappingstep 0 - pre-processing, 1 - post-processing
        @param experimentname individual name for the experiment 
        @param mappinglog name of the Mapping logfile
        @param ignoredb whether or not the database should be ignored
        @param dbip ip of the structural database
        @param dbport port of the structural database
        @param jsons path to the JSON backup files
        '''
        QtGui.QWidget.__init__(self)
        self.ui = uic.loadUi(MAPPINGINTERACTIVEPATH+'ui/interactivemappingwidget.ui',self)

        self.statistics = statistics
        self.statsplotter = statisticplot.Statisticplotter(STATISTICSFOLDER)
        self.experimentname = experimentname
        self.mappinglog = mappinglog
        
        # connect status
        self.dbcon = None 
        self.db = None
        self.ignoredb = ignoredb
        self.dbip = dbip
        self.dbport = dbport
        self.jsons = jsons
    
        self.devnull = open(os.devnull, 'wb')

        '''
        NA statistics
        '''
        
        fan_out = mappingutilities.vectorInt()
        fan_in = mappingutilities.vectorInt()
        self.statistics.getFanOutVector(fan_out)
        self.statistics.getFanInVector(fan_in)
        #numpy.savetxt('output/fan_out.dat',numpy.array(fan_out),fmt='%d')
        #numpy.savetxt('output/fan_in.dat',numpy.array(fan_in),fmt='%d')
        self.statsplotter.set_fan_in(fan_in)
        self.statsplotter.set_fan_out(fan_out)

        self.gridLayoutNA = QtGui.QGridLayout()
        self.ui.tabNA.setLayout(self.gridLayoutNA)
        self.ui.tabNA.setDisabled(True)
    
        self.na_tabs = QtGui.QTabWidget()
        self.ui.gridLayoutNA.addWidget(self.na_tabs,0,0,1,2)
        
        # fan-in/fan-out scatter plot
        self.fanin_fanout_scatter_view = graphicsViewFigure(self)
        #self.gridLayoutNA.addWidget(self.fanin_fanout_scatter_view,0,0,10,10)
        self.na_tabs.addTab(self.fanin_fanout_scatter_view, "Fan-In/-Out Scatter")
        
        # fan-in groups
        self.fanin_groups_view = graphicsViewFigure(self)
        #self.gridLayoutNA.addWidget(self.fanin_groups_view,0,10,5,5)
        self.na_tabs.addTab(self.fanin_groups_view, "Fan-In Groups")
        
        # HICANN Groups
        self.hicann_groups_view = graphicsViewFigure(self)
        #self.ui.gridLayoutNA.addWidget(self.hicann_groups_view,5,10,5,5)
        self.na_tabs.addTab(self.hicann_groups_view, "HICANN Groups")
        
        # A-Priori Loss info
        self.apriori_loss_label = QtGui.QLabel()
        self.ui.gridLayoutNA.addWidget(self.apriori_loss_label,10,0,1,1)
        
        self.apriori_loss_value = QtGui.QLineEdit()
        self.apriori_loss_value.setReadOnly(True)
        self.ui.gridLayoutNA.addWidget(self.apriori_loss_value,10,1,1,1)
        
        # cluster factors
        # a-priori losses
        # connection density
        # connection matrix
        # connectivity tables

        '''
        HMF overview
        '''
        self.gridLayoutHMF = QtGui.QGridLayout()
        self.ui.tabHMF.setLayout(self.gridLayoutHMF)
        self.ui.tabHMF.setDisabled(True)
        self.ui.tabHMF.setEnabled(False)

        # Tree-View of HMF structure from the MongoDB
        self.hmf_tree = treeHMF()
        self.ui.gridLayoutHMF.addWidget(self.hmf_tree,0,0,1,1)
        self.ui.gridLayoutHMF.setColumnMinimumWidth(0,250)

        # add a new tab widget for the wafers
        # each tabs holds a wafer and for each wafer an 
        # FPGAs, DNCs & HICANNs tab which hold abstract views 
        # with elements that can be selected
        self.hmf_tabs = QtGui.QTabWidget()
        self.ui.gridLayoutHMF.addWidget(self.hmf_tabs,0,1,1,1)
        self.ui.gridLayoutHMF.setColumnStretch(1,250)

        # loop through the wafer collection and 
        # for each existing wafer create a tab
        self.hmf_wafer_tabs = []
        self.hmf_fpga_tabs = []
        self.hmf_dnc_tabs = []
        self.hmf_hicann_tabs = []
        
        for wafer_id in range(0, WAFER_COUNT_HMF):
            self.hmf_wafer_tabs.append(QtGui.QTabWidget(parent=self.hmf_tabs))
            self.hmf_tabs.addTab(self.hmf_wafer_tabs[-1],str(wafer_id+1))
        
        '''
        Mapping Info
        '''
        self.gridLayoutMAP = QtGui.QGridLayout()
        self.ui.tabMAP.setLayout(self.gridLayoutMAP)
        self.ui.tabMAP.setDisabled(True)
        self.ui.tabMAP.setEnabled(False)

        self.map_tabs = QtGui.QTabWidget()
        self.ui.gridLayoutMAP.addWidget(self.map_tabs,0,0,1,1)
        #self.ui.gridLayoutMAP.setColumnStretch(1,250)
        
        # loop through the wafer collection and 
        # for each existing wafer create a tab
        self.map_wafer_tabs = []
        self.map_fpga_tabs = []
        self.map_dnc_tabs = []
        self.map_hicann_tabs = []
        
        for wafer_id in range(0, WAFER_COUNT_HMF):
            self.map_wafer_tabs.append(QtGui.QTabWidget(parent=self.map_tabs))
            self.map_tabs.addTab(self.map_wafer_tabs[-1],str(wafer_id+1))

        if mappingstep == STEP_PREPROCESSING :

            #self.ui.tabNA.setDisabled(False)
            self.ui.tabNA.setDisabled(False)
            self.ui.tabHMF.setDisabled(False)
            self.ui.tabWidget.setCurrentWidget(self.ui.tabHMF)
            
            # NA stats
            self.statsplotter.hicann_fan_in_histogramm('fanin_groups.png')
            self.statsplotter.hicann_config_groups('hicann_groups.png')
            self.statsplotter.fanin_fanout_scatter_plot('fan_in_out_scatter.png')

            self.fanin_groups_view.addFigure(QtGui.QGraphicsPixmapItem(QtGui.QPixmap(STATISTICSFOLDER+'fanin_groups.png')))
            self.fanin_fanout_scatter_view.addFigure(QtGui.QGraphicsPixmapItem(QtGui.QPixmap(STATISTICSFOLDER+'fan_in_out_scatter.png')))
            self.hicann_groups_view.addFigure(QtGui.QGraphicsPixmapItem(QtGui.QPixmap(STATISTICSFOLDER+'hicann_groups.png')))
            self.apriori_loss_label.setText("A-Priori Synapse Loss")
            self.apriori_loss_value.setText(str(self.statsplotter.get_aprioriloss()))
            
            # open the database and populate the views 
            # for the available wafers with info from database
            self._open_db()
            wafer_collection = self.db.WAFER
            for wafer_id in range(0, WAFER_COUNT_HMF):
                wafer = wafer_collection.find_one({"logicalNumber":int(wafer_id)})
                
                if wafer != None :
                    
                    self.hmf_fpga_tabs.append(viewWaferAvailabilityFPGAs(statistics,parent=self.hmf_wafer_tabs[wafer_id]))
                    self.hmf_wafer_tabs[wafer_id].addTab(self.hmf_fpga_tabs[-1], "FPGAs")
                    
                    self.hmf_dnc_tabs.append(viewWaferAvailabilityDNCs(statistics,parent=self.hmf_wafer_tabs[wafer_id]))
                    self.hmf_wafer_tabs[wafer_id].addTab(self.hmf_dnc_tabs[-1], "DNCs")
                    
                    self.hmf_hicann_tabs.append(viewWaferAvailabilityHICANNs(statistics,parent=self.hmf_wafer_tabs[wafer_id]))
                    self.hmf_wafer_tabs[wafer_id].addTab(self.hmf_hicann_tabs[-1], "HICANNs")

                    # from tree to wafer views
                    QtCore.QObject.connect(self.hmf_tree, QtCore.SIGNAL('itemClicked(QTreeWidgetItem*, int)'),self.hmf_fpga_tabs[-1].treeSelectionHandler)
                    QtCore.QObject.connect(self.hmf_tree, QtCore.SIGNAL('itemClicked(QTreeWidgetItem*, int)'),self.hmf_dnc_tabs[-1].treeSelectionHandler)
                    QtCore.QObject.connect(self.hmf_tree, QtCore.SIGNAL('itemClicked(QTreeWidgetItem*, int)'),self.hmf_hicann_tabs[-1].treeSelectionHandler)

                    # from wafer views to tree 
                    QtCore.QObject.connect(self.hmf_fpga_tabs[-1], QtCore.SIGNAL('itemSelected'),self.hmf_tree.graphicsSelectionHandler)
                    QtCore.QObject.connect(self.hmf_dnc_tabs[-1], QtCore.SIGNAL('itemSelected'),self.hmf_tree.graphicsSelectionHandler)
                    QtCore.QObject.connect(self.hmf_hicann_tabs[-1], QtCore.SIGNAL('itemSelected'),self.hmf_tree.graphicsSelectionHandler)
                    
                    # populate the views
                    # first the wafer views which once populated hold FPGAs, DNCs, HICANNs identified by id
                    # second the tree which searches the database and signals information
                    # to the wafer view
                    self.hmf_fpga_tabs[-1].populateWaferViewFPGAs(database=self.db,wafer_id=wafer_id)
                    self.hmf_dnc_tabs[-1].populateWaferViewDNCs(database=self.db,wafer_id=wafer_id)
                    self.hmf_hicann_tabs[-1].populateWaferViewHICANNs(database=self.db,wafer_id=wafer_id)
                    
                    #get the views and store them in the $STATISTICSFOLDER
                    view_pixmap = self.hmf_fpga_tabs[-1].getViewAsPixMap()
                    view_pixmap.save(STATISTICSFOLDER+'w'+str(wafer_id)+'_fpga_pre.png')
                    view_pixmap = self.hmf_dnc_tabs[-1].getViewAsPixMap()
                    view_pixmap.save(STATISTICSFOLDER+'w'+str(wafer_id)+'_dnc_pre.png')
                    view_pixmap = self.hmf_hicann_tabs[-1].getViewAsPixMap()
                    view_pixmap.save(STATISTICSFOLDER+'w'+str(wafer_id)+'_hicann_pre.png')
                    
                else :
                    # placeholder for empty elements
                    view_pixmap = QtGui.QPixmap(MAPPINGINTERACTIVEPATH+'pics/empty_report_view.png').scaled(1200,1200)
                    view_pixmap.save(STATISTICSFOLDER+'w'+str(wafer_id)+'_fpga_pre.png')
                    view_pixmap.save(STATISTICSFOLDER+'w'+str(wafer_id)+'_dnc_pre.png')
                    view_pixmap.save(STATISTICSFOLDER+'w'+str(wafer_id)+'_hicann_pre.png')

            # connect the signals
            QtCore.QObject.connect(self.hmf_tree, QtCore.SIGNAL('itemClicked(QTreeWidgetItem*, int)'),self.treeSelectionHandler)
            self.hmf_tree.populateTree(self.db)

        elif mappingstep == STEP_POSTPROCESSING :

            self.ui.tabMAP.setDisabled(False)
            self.ui.tabWidget.setCurrentWidget(self.ui.tabMAP)

            self._open_db()

            wafer_collection = self.db.WAFER
            for wafer_id in range(0, WAFER_COUNT_HMF):
                wafer = wafer_collection.find_one({"logicalNumber":int(wafer_id)})
                if wafer != None :

                    self.map_fpga_tabs.append(viewWaferUtilisationFPGAs(statistics=self.statistics,wafer_id=wafer_id))
                    self.map_wafer_tabs[wafer_id].addTab(self.map_fpga_tabs[-1], "FPGAs")

                    self.map_dnc_tabs.append(viewWaferUtilisationDNCs(statistics=self.statistics,wafer_id=wafer_id))
                    self.map_wafer_tabs[wafer_id].addTab(self.map_dnc_tabs[-1], "DNCs")

                    self.map_hicann_tabs.append(viewWaferUtilisationHICANNs(statistics=self.statistics,wafer_id=wafer_id))
                    self.map_wafer_tabs[wafer_id].addTab(self.map_hicann_tabs[-1], "HICANNs")

                    #get the views and store them in the $STATISTICSFOLDER
                    view_pixmap = self.map_fpga_tabs[wafer_id].getViewAsPixMap()
                    view_pixmap.save(STATISTICSFOLDER+'w'+str(wafer_id)+'_fpga_post.png')
                    view_pixmap = self.map_dnc_tabs[wafer_id].getViewAsPixMap()
                    view_pixmap.save(STATISTICSFOLDER+'w'+str(wafer_id)+'_dnc_post.png')
                    view_pixmap = self.map_hicann_tabs[wafer_id].getViewAsPixMap()
                    view_pixmap.save(STATISTICSFOLDER+'w'+str(wafer_id)+'_hicann_post.png')

                else :
                    # placeholder for empty elements
                    view_pixmap = QtGui.QPixmap(MAPPINGINTERACTIVEPATH+'pics/empty_report_view.png').scaled(1200,1200)
                    view_pixmap.save(STATISTICSFOLDER+'w'+str(wafer_id)+'_fpga_post.png')
                    view_pixmap.save(STATISTICSFOLDER+'w'+str(wafer_id)+'_dnc_post.png')
                    view_pixmap.save(STATISTICSFOLDER+'w'+str(wafer_id)+'_hicann_post.png')
            '''
            self.graphics_view_hicann_detailed = viewHICANNUtilisationDetailed(statistics=self.statistics,wafer_id=0)
            self.ui.gridLayoutMAP.addWidget(self.graphics_view_hicann_detailed,0,1)
        
            # signal when a HICANN was clicked to update 
            # the utilisation in the detailed view
            QtCore.QObject.connect(self.graphics_view_hicann_array, QtCore.SIGNAL('request_update_detailed_view'),self.graphics_view_hicann_detailed.update_detailed_view)   
            '''
            self._create_mapping_log()
        else :
            raise NameError('InteractiveMapping::ERROR, invalid Mapping step')
    
    def treeSelectionHandler(self, item, column) :
        '''
        handler to switch to the right wafer tab
        
        @param item item in the HMF tree
        @param column column in the HMF tree table
        
        '''
# FIXME -- ME: the tab reiter is not changed and the treehandler is not called on tree topitem (wafer) click
        if item.type() == WAFERTREEITEMTYPE :
            self.hmf_tabs.setCurrentWidget(self.hmf_wafer_tabs[int(item.text(0))])
        else :
            self.hmf_tabs.setCurrentWidget(self.hmf_wafer_tabs[int(item.text(1))])

    def _create_mapping_log(self, with_mapping_quality=False, with_neural_network_statistics=False) :
        """
        create a MappingLog in pdf format
        """
        
        import time
        # open a printer
        self.printer = QtGui.QPrinter(QtGui.QPrinter.HighResolution)
        self.printer.setOutputFormat(QtGui.QPrinter.PdfFormat)
        self.printer.setPaperSize(QtGui.QPrinter.A4)
        self.printer.setOutputFileName(STATISTICSFOLDER + str(time.strftime('%y%m%d_%H%M_MappingReport.pdf')))

        # conduct the report
        self.painter = QtGui.QPainter(self.printer)
        '''
        first page NNA statistics and numbers
        '''
        self.painter.drawPixmap(7800,200,QtGui.QPixmap(MAPPINGINTERACTIVEPATH+'pics/bs_logo.png').scaled(800,800))
        self.painter.drawText(QtCore.QPointF(300,800), 'Mapping Report generated on '+str(time.strftime('%y/%m/%d at %H:%M'))+'     page 1/2')
        self.painter.drawText(QtCore.QPointF(300,1000), '  Experiment: "' +  str(self.experimentname)+'"')
        
        current_font = self.painter.font()
        self.painter.setFont(QtGui.QFont('courier',10))
        self.painter.drawText(QtCore.QPointF(300,1300), 'Neural Network: mapped / total elements')
        self.painter.drawText(QtCore.QPointF(300,1500), '  neurons:          '+ str(self.statistics.GetMappedNeuronCount()).rjust(10) + ' / ' + str(self.statistics.GetBioNeuronCount()))
        self.painter.drawText(QtCore.QPointF(300,1700), '  synapses:         '+ str(self.statistics.GetMappedSynapseCount()).rjust(10) + ' / ' + str(self.statistics.GetBioSynapseCount()))
        self.painter.drawText(QtCore.QPointF(300,1900), '  stimuli:          '+ str(self.statistics.GetMappedStimuliCount()).rjust(10) + ' / ' + str(self.statistics.GetBioStimuliCount()))
        self.painter.drawText(QtCore.QPointF(300,2100), '  stimuli synapses: '+ str(self.statistics.GetMappedStimuliSynapseCount()).rjust(10) + ' / ' + str(self.statistics.GetBioStimuliSynapseCount()))

        self.painter.drawText(QtCore.QPointF(300,2400), 'Losses: actual loss / loss limit specified by user')
        self.painter.drawText(QtCore.QPointF(300,2600), '   neurons:  '+ "{:.3f}".format(self.statistics.GetNeuronLoss()) + ' / '+ "{:.3f}".format(self.statistics.GetMaxNeuronLoss()))
        self.painter.drawText(QtCore.QPointF(300,2800), '   synapses: '+ "{:.3f}".format(self.statistics.GetSynapseLoss()) + ' / '+ "{:.3f}".format(self.statistics.GetMaxSynapseLoss()))
    
        if with_mapping_quality:
            self.painter.drawText(QtCore.QPointF(300,3500), ' Mapping Quality: ')
            self.painter.drawText(QtCore.QPointF(300,3700), '   Quality: '+"{:.2f}".format(self.statistics.GetMappingQuality()))
            componentsstring = "{"
            componentsstring += ' q_PR:'+"{:.2f}".format(self.statistics.GetPlaceRouteQuality())+','
            componentsstring += ' q_T:'+"{:.2f}".format(self.statistics.GetTransformationQuality())+','
            componentsstring += ' e_HW:'+"{:.2f}".format(self.statistics.GetHardwareEfficiency())+' }'
            self.painter.drawText(QtCore.QPointF(300,3900), '   Components: ' + componentsstring )
            weightstring = "{"
            weightstring += ' G_PR:'+"{:.2f}".format(self.statistics.GetPlaceRouteQualityWeight())+','
            weightstring += ' G_T:'+"{:.2f}".format(self.statistics.GetTransformationQualityWeight())+','
            weightstring += ' G_HW:'+"{:.2f}".format(self.statistics.GetHardwareEfficiencyWeight())+' }'
            self.painter.drawText(QtCore.QPointF(300,4100), '   Weights: ' + weightstring )

        self.painter.drawText(QtCore.QPointF(300,4400), 'Algorithm Sequences: ')
        self.painter.drawText(QtCore.QPointF(300,4600), '   Strategy: '+self.statistics.GetMappingStrategy())

        sequences = ['System','Wafer','Hicann']
        lineCnt = 0
        for sequence in sequences :
            self.painter.drawText(QtCore.QPointF(300,4800+lineCnt*200), '   '+str(sequence))
            algoList = (self.statistics.GetAlgorithmSequence(sequence).replace(' ','')).split('>')
            lineCnt += 1
            for algo in algoList :
                self.painter.drawText(QtCore.QPointF(300,4800+lineCnt*200), '       '+str(algo))
                lineCnt += 1

        self.painter.setFont(current_font)

        if with_neural_network_statistics:
            '''
            draw NNA statistics
            '''
            self.painter.drawPixmap(500,10700,QtGui.QPixmap(MAPPINGINTERACTIVEPATH+'pics/bs_logo.png').scaled(2600,2600))
            self.painter.drawPixmap(500,10000,QtGui.QPixmap(STATISTICSFOLDER+'fan_in_out_scatter.png').scaled(2600,2600))
            self.painter.drawPixmap(3100,10000,QtGui.QPixmap(STATISTICSFOLDER+'fanin_groups.png').scaled(2600,2600))
            self.painter.drawPixmap(5900,10000,QtGui.QPixmap(STATISTICSFOLDER+'hicann_groups.png').scaled(2600,2600))
        
        self.painter.drawText(QtCore.QPointF(50,13400),' For more information see: '+ str(self.mappinglog)) 
        
        '''
        second page mainly mapping images
        '''
        self.printer.newPage()
        self.painter.drawPixmap(7800,200,QtGui.QPixmap(MAPPINGINTERACTIVEPATH+'pics/bs_logo.png').scaled(800,800))
        self.painter.drawText(QtCore.QPointF(300,800), 'Mapping Report generated on '+str(time.strftime('%y/%m/%d at %H:%M'))+'     page 2/2')
        self.painter.drawText(QtCore.QPointF(300,1000), '  Experiment: "' +  str(self.experimentname)+'"')
        
        self.painter.drawText(QtCore.QPointF(500,1500), 'BEFORE Mapping')
        self.painter.drawText(QtCore.QPointF(4600,1500), 'AFTER Mapping')

        self.painter.drawText(QtCore.QPointF(500,1700), 'FPGA')
        self.painter.drawText(QtCore.QPointF(1800,1700), 'DNC')
        self.painter.drawText(QtCore.QPointF(3100,1700), 'HICANN')
        
        self.painter.drawText(QtCore.QPointF(4600,1700), 'FPGA')
        self.painter.drawText(QtCore.QPointF(5900,1700), 'DNC')
        self.painter.drawText(QtCore.QPointF(7200,1700), 'HICANN')
        
        for wafer_id in range(0, WAFER_COUNT_HMF):
            
            self.painter.drawText(QtCore.QPointF(100,2550+wafer_id*1300), 'w'+str(wafer_id))
            
            self.painter.drawPixmap(500,1800+wafer_id*1300, QtGui.QPixmap(STATISTICSFOLDER+'w'+str(wafer_id)+'_fpga_pre.png'))
            self.painter.drawPixmap(1800,1800+wafer_id*1300, QtGui.QPixmap(STATISTICSFOLDER+'w'+str(wafer_id)+'_dnc_pre.png'))
            self.painter.drawPixmap(3100,1800+wafer_id*1300, QtGui.QPixmap(STATISTICSFOLDER+'w'+str(wafer_id)+'_hicann_pre.png'))
            
            self.painter.drawPixmap(4600,1800+wafer_id*1300, QtGui.QPixmap(STATISTICSFOLDER+'w'+str(wafer_id)+'_fpga_post.png'))
            self.painter.drawPixmap(5900,1800+wafer_id*1300, QtGui.QPixmap(STATISTICSFOLDER+'w'+str(wafer_id)+'_dnc_post.png'))
            self.painter.drawPixmap(7200,1800+wafer_id*1300, QtGui.QPixmap(STATISTICSFOLDER+'w'+str(wafer_id)+'_hicann_post.png'))

        # draw a few lines
        self.painter.setPen(QtGui.QPen(QtGui.QColor(),20,QtCore.Qt.DashLine))
        self.painter.drawLine(QtCore.QLineF(QtCore.QPointF(4450,1800),QtCore.QPointF(4450,9450)))
        self.painter.drawLine(QtCore.QLineF(QtCore.QPointF(500,9600),QtCore.QPointF(8450,9600)))
        
        '''
        draw the legends
        '''
        outline_color = QtGui.QColor()
        filling_color = QtGui.QColor()
        filling_color.setAlpha(100)
        legendx = 550
        legendy = 9800
        current_font = self.painter.font()
        
        self.painter.setFont(QtGui.QFont('univers',8))
        self.painter.setPen(QtGui.QPen(QtGui.QColor(),2,QtCore.Qt.SolidLine))
        # legend for the allocations
        self.painter.drawText(QtCore.QPointF(legendx,legendy), 'allocation:')
        allocation_colors = ["#FF0000","#00FF00","#0000FF","#FFFF00"]
        allocation_color_names = ['locked','available','user','mapper']
        for c in  range(4) :
            outline_color.setNamedColor(allocation_colors[c])
            filling_color.setNamedColor(allocation_colors[c])
            self.painter.setPen(QtGui.QPen(outline_color,4,QtCore.Qt.SolidLine))
            self.painter.setBrush(QtGui.QBrush(filling_color))
            self.painter.drawRect(QtCore.QRect(QtCore.QPoint(legendx+800+c*800,legendy),QtCore.QPoint(legendx+900+c*800,legendy-100)))
            self.painter.setPen(QtGui.QPen(QtGui.QColor(),2,QtCore.Qt.SolidLine))
            self.painter.drawText(QtCore.QPointF(legendx+950+c*800,legendy), allocation_color_names[c])
        
        # legend for the utilization
        self.painter.setPen(QtGui.QPen(QtGui.QColor(),2,QtCore.Qt.SolidLine))
        self.painter.drawText(QtCore.QPointF(legendx+4500,legendy), 'utilization: 0.0')
        for h in range(1,11) :
            outline_color.setHsl(100-10*h,255,155)
            filling_color.setHsl(100-10*h,255,155)
            self.painter.setPen(QtGui.QPen(outline_color,4,QtCore.Qt.SolidLine))
            self.painter.setBrush(QtGui.QBrush(filling_color))
            self.painter.drawRect(QtCore.QRect(QtCore.QPoint(legendx+5400+h*100,legendy),QtCore.QPoint(legendx+5500+h*100,legendy-100)))
        self.painter.setPen(QtGui.QPen(QtGui.QColor(),2,QtCore.Qt.SolidLine))
        self.painter.drawText(QtCore.QPointF(legendx+6550,legendy), '1.0')
        self.painter.setFont(current_font)
        
    
        self.painter.drawText(QtCore.QPointF(50,13400),' For more information see: '+ str(self.mappinglog)) 
        
        self.painter.end()
        
    def _open_db(self) :
        """
        get the structural data either from the database or from its 
        JSON backup
        """

        '''
        First attempt to connect to the database 
        if the original data should be ignored insert the JSON data
        if this is not possible try to 
        read in JSON files into a new database
        if this also fails drop out
        '''
        try :
            self.dbcon = pymongo.Connection(str(self.dbip),int(self.dbport))
            print('Connected to database on '+str(self.dbip)+':'+str(self.dbport))
            if not self.ignoredb :
                self.db = self.dbcon.calibrationDB
                self.db.collection_names()
            else :
                self.dbcon.drop_database(self.dbcon.interactiveDB)
                self.db = self.dbcon.interactiveDB
                self._insert_json()
                self.db.collection_names()
            return
        except :
            print('WARNING: Could not connect to database on '+str(self.dbip)+':'+str(self.dbport)+' so creating one on ' + str(self.dbip)+":"+str(INTERACTIVEDBPPORT))
        
        try :
            subprocess.call("rm -rf "+ INTERACTIVEDBPATH)
            os.makedirs(INTERACTIVEDBDATA)
            os.makedirs(INTERACTIVEDBLOGS)
        except :
            print('WARNING: Database dirs already exist')
        mongodstartstring = "mongod --fork --rest --dbpath "+str(INTERACTIVEDBDATA)+" --port "+str(INTERACTIVEDBPPORT)+" --logpath "+str(INTERACTIVEDBLOGFILE)
        subprocess.call(mongodstartstring, shell=True, stdout=self.devnull, stderr=subprocess.STDOUT)
        print('INFO: Attempting to connect to database on '+str(self.dbip)+':'+str(INTERACTIVEDBPPORT))
        # TODO -- ME: find another solution to wait
        # we have to try until the forked db process is ready
        for n in range (0,100) :
            try :           
                self.dbcon = pymongo.Connection(str(self.dbip),int(INTERACTIVEDBPPORT))
                if self.dbcon :
                    print('INFO: Connected to database on '+str(self.dbip)+':'+str(INTERACTIVEDBPPORT))
                    self.dbcon.drop_database(self.dbcon.interactiveDB)
                    self.db = self.dbcon.interactiveDB
                    self._insert_json()
                    self.db.collection_names()
                    return
            except :
                print (".")

        # if we did not succeed clean up
        print ("ERROR: Could neither connect to the given DB nor create one")
        self._cleanup_db()
        
# TODO -- ME: exits scripts completely, but should only self.destroy()
        sys.exit(-1)

    def _close_db(self) :
        # if working on the normal database just close
        # if we ignored the original database but are connected 
        # erase the inserted data from there
        # if we created started a mongodb then 
        # shut it down and erase the data
        try : 
            self.dbcon.drop_database(self.dbcon.interactiveDB)
            del self.dbcon
            self._cleanup_db()
        except :
            print("WARNING: PLS check if all interactive mapping created db and content is gone.")
            
    def _cleanup_db(self) :
        subprocess.call('mongo --eval "db.getSiblingDB(\'admin\').shutdownServer()" --port '+str(INTERACTIVEDBPPORT), shell=True, stdout=self.devnull, stderr=subprocess.STDOUT)
        subprocess.call('rm -rf mongodb', shell=True, stdout=self.devnull, stderr=subprocess.STDOUT)
        
    def _insert_json(self) :
        '''
        deserialize JSON objects and 
        insert into database
        '''
        wafer_collection = self.db.WAFER
        wafer_collection.insert(self._get_json_string(self.jsons+'/structural/WAFER.json')['wafer'])
        fpga_collection = self.db.FPGA
        fpga_collection.insert(self._get_json_string(self.jsons+'/structural/FPGA.json')['fpga'])
        dnc_collection = self.db.DNC
        dnc_collection.insert(self._get_json_string(self.jsons+'/structural/DNC.json')['dnc'])
        hicann_collection = self.db.HICANN
        hicann_collection.insert(self._get_json_string(self.jsons+'/structural/HICANN.json')['hicann'])
    
    def _get_json_string(self,jsonfilename):
        '''
        helper to read files in JSON format
        '''
        #print jsonfilename
        jsonfilehandle = open(jsonfilename,'r')
        jsonstring  = jsonfilehandle.read()
        jsondata = json.loads(jsonstring)
        return dict(jsondata)
