from PyQt4 import QtCore
from PyQt4 import QtGui

import pymongo
import os

MAPPINGINTERACTIVEPATH = os.environ['SYMAP2IC_PATH']+'/components/pynnhw/src/hardware/brainscales/mappinginteractive/'

# user types for the HMF tree items
WAFERTREEITEMTYPE = 1001
FPGATREEITEMTYPE = 1002
DNCTREEITEMTYPE = 1003
HICANNTREEITEMTYPE = 1004

WAFER_COUNT_HMF = 8

class treeHMF(QtGui.QTreeWidget) :
    '''
    a customized Qt tree-view-widget
    holding the HMF hierarchy
    '''
    def __init__(self,parent=None) :
        QtGui.QTreeWidget.__init__(self)
        
    def populateTree(self,db) : 
        '''
        fill the tree with structural data from
        BSON objects
        '''
        # tree layout
        self.setColumnCount(4)
        self.setHeaderLabels(['W/F/D/H IDs','','x','y'])
        self.setColumnWidth(0,150)
        self.setColumnWidth(1,0) # holds the parent wafer and is not shown
        self.setColumnWidth(2,25)
        self.setColumnWidth(3,25)
        
        # collections from the mongo db
        wafer_collection = db.WAFER
        fpga_collection = db.FPGA
        dnc_collection = db.DNC
        hicann_collection = db.HICANN
        
        # filling the tree
        # wafers
    
        for wafer_id in range(0, WAFER_COUNT_HMF):
            wafer = wafer_collection.find_one({"logicalNumber":int(wafer_id)})
            self.wafer_logical = int(wafer_id)
            self.waferitem = QtGui.QTreeWidgetItem([str(wafer_id)],WAFERTREEITEMTYPE)
            self.waferitem.setIcon(0,QtGui.QIcon(MAPPINGINTERACTIVEPATH+'pics/icons/wafer.png'))
            self.addTopLevelItem(self.waferitem)
            if wafer != None :
                # wafers -> fpgas
                fpgas = fpga_collection.find({ "parent_wafer" : self.wafer_logical })
                for fpga in fpgas:
                    for key,value in fpga.iteritems():
                        if key == 'logicalNumber' :
                            self.fpga_logical = int(value)
                            self.fpgaitem = QtGui.QTreeWidgetItem([str(value),str(self.wafer_logical)],FPGATREEITEMTYPE)
                            self.fpgaitem.setIcon(0,QtGui.QIcon(MAPPINGINTERACTIVEPATH+'pics/icons/fpga.png'))
                            self.waferitem.addChild(self.fpgaitem)
                            # fpgas->dncs
                            dncs = dnc_collection.find({ "parent_wafer" : self.wafer_logical , "parent_fpga" : self.fpga_logical})
                            for dnc in dncs:
                                for key,value in dnc.iteritems():
                                    if key == 'reticleId' :
                                        self.dnc_logical = int(value)
                                        self.dncitem = QtGui.QTreeWidgetItem([str(value),str(self.wafer_logical)],DNCTREEITEMTYPE)
                                        self.dncitem.setIcon(0,QtGui.QIcon(MAPPINGINTERACTIVEPATH+'pics/icons/dnc.png'))
                                        self.fpgaitem.addChild(self.dncitem)
                                    if key == 'fpgaDncChannel' :
                                        # dncs->hicanns
                                        self.fpga_dnc_channel = int(value)
                                        hicanns = hicann_collection.find({ "parent_wafer" : self.wafer_logical , "parent_fpga" : self.fpga_logical, "parent_dnc" : self.fpga_dnc_channel})
                                        for hicann in hicanns:
                                            for key,value in hicann.iteritems() :
                                                if key == 'configId' :
                                                    self.hicann_configId = int(value)
                                                if key == 'hicannX' :
                                                    self.hicann_x = int(value) 
                                                if key == 'hicannY' :
                                                    self.hicann_y = int(value)

                                            self.hicannitem = QtGui.QTreeWidgetItem([str(self.hicann_configId),str(self.wafer_logical),str(self.hicann_x),str(self.hicann_y)],HICANNTREEITEMTYPE)
                                            self.hicannitem.setIcon(0,QtGui.QIcon(MAPPINGINTERACTIVEPATH+'pics/icons/hicann.png'))
                                            self.dncitem.addChild(self.hicannitem)
            else :
                self.waferitem.setDisabled(True)
    def graphicsSelectionHandler(self,itemtype,parent_wafer,logical_id) :
        '''
        
        select the item with id
        
        @param itemtype user item type
        @param parent_wafer logical id of the parent wafer
        @param parent_wafer logical id of the element
        '''
        iterator = QtGui.QTreeWidgetItemIterator(self);
        while (iterator.value()) :
            item = iterator.value()
            if item.type() == itemtype and int(item.text(0)) == logical_id and int(item.text(1)) == parent_wafer :
                self.setCurrentItem(item)
                item.setSelected(True)
            else :
                item.setSelected(False)
            iterator += 1