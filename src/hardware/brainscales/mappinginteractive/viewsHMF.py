"""

 Figure & HMF graphic views

"""

import numpy

from PyQt4 import QtCore
from PyQt4 import QtGui

import pymongo

from itemsHMF import *

MAPPINGINTERACTIVEPATH = os.environ['SYMAP2IC_PATH']+'/components/pynnhw/src/hardware/brainscales/mappinginteractive/'

# user types for the HMF tree items
WAFERTREEITEMTYPE = 1001
FPGATREEITEMTYPE = 1002
DNCTREEITEMTYPE = 1003
HICANNTREEITEMTYPE = 1004

"""

 graphics view base 
 with zoom and panning functionality

"""

class viewBase(QtGui.QGraphicsView) :
    
    def __init__(self,parent=None) :
        
        QtGui.QGraphicsView.__init__(self)
        
        self.CurrentCenterPoint = QtCore.QPointF()
        self.LastPanPoint = QtCore.QPointF()
        
        self.Scene = QtGui.QGraphicsScene(self)
        self.setScene(self.Scene)
        
        self.setRenderHints(QtGui.QPainter.Antialiasing)
        #self.setRenderHints(QtGui.QPainter.SmoothPixmapTransform)

    def getViewAsPixMap(self):
        pixmap = QtGui.QImage(1200,1200,QtGui.QImage.Format_ARGB32)
        pixmap.fill(QtCore.Qt.white) # fill the pixmap with white
        imagePainter = QtGui.QPainter(pixmap)
        imagePainter.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing | QtGui.QPainter.SmoothPixmapTransform)
        self.Scene.render(imagePainter)
        return pixmap
    
    def SetCenter(self, centerPoint) :
       
       # size of the view in scene coordinates
       visibleArea = self.mapToScene(self.rect()).boundingRect()
       
       # size of the the scene
       sceneBounds = self.sceneRect()
       
       boundX = visibleArea.width() / 2.0
       boundY = visibleArea.height() / 2.0
       boundWidth = sceneBounds.width() - 2.0 * boundX
       boundHeight = sceneBounds.height() - 2.0 * boundY
       bounds = QtCore.QRectF(boundX, boundY, boundWidth, boundHeight);

       if bounds.contains(centerPoint) :
          self.CurrentCenterPoint = centerPoint
       else :
          # We need to clamp or use the center of the screen
          if visibleArea.contains(sceneBounds) :
              # Use the center of scene ie. we can see the whole scene
              self.CurrentCenterPoint = sceneBounds.center()
          else :
              self.CurrentCenterPoint = centerPoint;

              # We need to clamp the center. The centerPoint is too large
              if centerPoint.x() > (bounds.x() + bounds.width()) :
                  self.CurrentCenterPoint.setX(bounds.x() + bounds.width())
              else :
                 if centerPoint.x() < bounds.x() :
                    self.CurrentCenterPoint.setX(bounds.x())

              if centerPoint.y() > (bounds.y() + bounds.height()) :
                 self.CurrentCenterPoint.setY(bounds.y() + bounds.height())
              else :
                 if centerPoint.y() < bounds.y() :
                    self.CurrentCenterPoint.setY(bounds.y())

       # Update the scrollbars
       self.centerOn(self.CurrentCenterPoint)

    def GetCenter(self) :
        
        return self.CurrentCenterPoint

    def mouseReleaseEvent(self, event) :
        
        # panning
        if event.button() == QtCore.Qt.RightButton :
            self.setCursor(QtCore.Qt.ArrowCursor)
            self.LastPanPoint = QtCore.QPoint()

    def mouseMoveEvent(self, event) :
        
        if not self.LastPanPoint.isNull() :
            delta = QtCore.QPointF(self.mapToScene(self.LastPanPoint) - self.mapToScene(event.pos()))
            self.LastPanPoint = event.pos()
            self.SetCenter(self.GetCenter() + delta)

    def wheelEvent(self, event) :

        pointBeforeScale = QtCore.QPointF(self.mapToScene(event.pos()))
        
        screenCenter = QtCore.QPointF(self.GetCenter())
        scaleFactor = 1.15 # zoom speed
        if event.delta() > 0 :  # in
            self.scale(scaleFactor, scaleFactor);
        else : # out
            self.scale( 1.0/scaleFactor , 1.0/scaleFactor )
        # Get the position after scaling, in scene coords
        pointAfterScale = QtCore.QPointF(self.mapToScene(event.pos()))
        # Get the offset of how the screen moved
        offset =  QtCore.QPointF(pointBeforeScale - pointAfterScale)
        # Adjust to the new center for correct zooming
        newCenter = QtCore.QPointF(screenCenter + offset)
        self.SetCenter(newCenter)

    def resizeEvent(self, event) :
        # Get the rectangle of the visible area in scene coords
        visibleArea = QtCore.QRectF(self.mapToScene(self.rect()).boundingRect())
        self.SetCenter(visibleArea.center())

"""

  graphics view for a figure

"""
class graphicsViewFigure(viewBase) :

    def __init__(self,parent=None) :
        viewBase.__init__(self)
    
        self.scene_rectangle = None
    
    def addFigure(self, figure) :
        # add item at the scene and match the scenes bounding box
        # to the size of the figure 
        self.Scene.addItem(figure)
        self.scene_rectangle = figure.boundingRect()
        scenewidth = self.scene_rectangle.width()
        sceneheight = self.scene_rectangle.height()
        #self.setSceneRect(0,0,scenewidth,sceneheight)        
        self.SetCenter(QtCore.QPointF(scenewidth/2,sceneheight/2))

    def mousePressEvent(self, event) :
        
        # panning 
        if event.button() == QtCore.Qt.RightButton :
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            self.LastPanPoint = event.pos()

    def resizeEvent(self,event) :
        self.fitInView(0, 0, self.scene_rectangle.width(),self.scene_rectangle.height())


"""

 graphics view for an wafer view

"""
class viewWafer(viewBase) :
    def __init__(self,parent=None) :
        viewBase.__init__(self)
        
        self.scene_backdrop_item_list = [] # holds the backdrop items
        self.scene_selectable_item_list = [] # holds the selectable items
        self.last_item = None # last selected item
        
        self.statistics = None
        self.db = None
        self.wafer_id = None
        
    def mousePressEvent(self, event) :
        # selecting
        if event.button() == QtCore.Qt.LeftButton :
            item = self.itemAt(event.pos())
            self._selector(item)

        # panning 
        if event.button() == QtCore.Qt.RightButton :
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            self.LastPanPoint = event.pos()

    def _selector(self,item) :
        '''
        helper to toggle the select status
        '''
        if self.last_item :
            if item == self.last_item :
                self.last_item.toggleSelected()
                self.last_item = None
            else :
                self.last_item.toggleSelected()
                item.toggleSelected()
                self.last_item = item
        else :
            item.toggleSelected()
            self.last_item = item

    # TODO -- debug resizing, panning, scaling stuff:
    def resizeEvent(self,event) :
        self.fitInView(0, 0, self.scene_rectangle.width(),self.scene_rectangle.height())
"""

 graphics view for the FPGA array

 the user can select FPGA elements in the view and
 unfold the corresponding element in the HMF tree
 
"""

LOCKED = 0
AVAILABLE = 1
SELECTED_USER = 2
SELECTED_MAPPER = 3

class viewWaferAvailabilityFPGAs(viewWafer) :

    def __init__(self,statistics,parent=None) :
        viewWafer.__init__(self)
        
        self.statistics = statistics

        # mask encoding the location
        # of the FPGAs on the PCB grid
        # 0 - empty, 
        # 1 - front,
        # 2 - back
        self.fpga_use_mask  = numpy.array([
            [0,1,2,1,0],
            [1,0,0,0,1],
            [2,0,0,0,2],
            [1,0,0,0,1],
            [0,1,2,1,0]]
        )
        # mask encoding the FPGA id in the system
        self.fpga_id_mask  = numpy.array([
            [0,9,2,8,0],
            [10,0,0,0,7],
            [3,0,0,0,1],
            [11,0,0,0,6],
            [0,4,0,5,0]]
        )

        for y in range(5)  :
            for x in range(5) :
                self.scene_backdrop_item_list.append(itemFPGABackdrop())
                self.scene_backdrop_item_list[-1].setImage(self.fpga_use_mask[y][x])
                self.scene_backdrop_item_list[-1].setPos(QtCore.QPointF(x*102,y*102))
                self.Scene.addItem(self.scene_backdrop_item_list[-1])
        self.scene_rectangle = self.sceneRect()
        self.SetCenter(QtCore.QPointF(self.scene_rectangle.width()/2,self.scene_rectangle.height()/2))
        
    def populateWaferViewFPGAs(self,database,wafer_id) :
        '''
        populate the FPGA view from the database to get the online and locked status and 
        from the HW model to get the allocation information
        
        FPGAs are marked as follows:
        
        red -- locked
        green -- available but not allocated for mapping green
        yellow --allocated by the mapping process
        
        '''

        self.db = database
        self.wafer_id = wafer_id

        fpga_collection = self.db.FPGA
        fpgas_used = self.statistics.GetFPGAUsedOnWafer(self.wafer_id)
        
        for y in range(5) :
            for x in range(5) :
                if self.fpga_use_mask[y][x] == 2 or self.fpga_use_mask[y][x] == 1 :
                    
                    self.scene_selectable_item_list.append(itemFPGASelectable())
                    self.scene_selectable_item_list[-1].setPos(QtCore.QPointF(x*102,y*102))
                    tooltipstring = "FPGA("+str(x)+","+str(y)+")\nID: "+str(self.fpga_id_mask[y][x])
                    self.scene_selectable_item_list[-1].setToolTip(tooltipstring)
                    self.scene_selectable_item_list[-1].setLogicalId(self.fpga_id_mask[y][x])
                    
                    fpga = fpga_collection.find_one({"logicalNumber":int(self.fpga_id_mask[y][x]), "parent_wafer": int(self.wafer_id)})
                    for key, value in fpga.iteritems() :
                        if key == 'online' :
                            if value == True :
                                self.scene_selectable_item_list[-1].setStatus(AVAILABLE)
                                for key, value in fpga.iteritems() :
                                    if key == 'locked' :
                                        if value == True :
                                            self.scene_selectable_item_list[-1].setStatus(LOCKED)
                                for fpga_used in fpgas_used :
                                    if fpga_used == self.fpga_id_mask[y][x] :
                                        self.scene_selectable_item_list[-1].setStatus(SELECTED_MAPPER)

                    self.Scene.addItem(self.scene_selectable_item_list[-1])

    def mousePressEvent(self, event) :
        if event.button() == QtCore.Qt.LeftButton :
            item = self.itemAt(event.pos())
            self.emit(QtCore.SIGNAL("itemSelected"),FPGATREEITEMTYPE,self.wafer_id,item.getLogicalId())
            super(viewWaferAvailabilityFPGAs, self).mousePressEvent(event)

    def treeSelectionHandler(self, item, column) :
        '''
        handler to find an FPGA item 
        in the scene via its type and logical id
        
        @param item item in the HMF tree
        @param column column in the HMF tree table
        
        '''
        if item.type() == FPGATREEITEMTYPE and int(item.text(1)) == self.wafer_id:
            for selectable_item in self.scene_selectable_item_list :
                if selectable_item.getLogicalId() == int(item.text(0)) :
                    super(viewWaferAvailabilityFPGAs, self)._selector(selectable_item)
                    self.parent().setCurrentWidget(self)
                    self.parent().setCurrentIndex(0)

"""

 graphics view for DNC array

"""
class viewWaferAvailabilityDNCs(viewWafer) :
    def __init__(self,statistics,parent=None) :
        viewWafer.__init__(self)
        
        self.statistics = statistics
        
        # mask encoding the location
        # 
        # of the DNCs
        # 0 - empty, 
        # 1 - not empty
        self.dnc_use_mask = numpy.array([
            [0,0,0,1,1,1,0,0,0],
            [0,0,1,1,1,1,1,0,0],
            [0,1,1,1,1,1,1,1,0],
            [1,1,1,1,1,1,1,1,1],
            [1,1,1,1,1,1,1,1,1],
            [0,1,1,1,1,1,1,1,0],
            [0,0,1,1,1,1,1,0,0],
            [0,0,0,1,1,1,0,0,0]]
        )
        self.dnc_id_mask = numpy.array([
            [0,0,0,1,4,5,0,0,0],
            [0,0,2,45,6,7,8,0,0],
            [0,44,43,3,11,11,10,14,0],
            [41,42,47,48,46,9,15,16,13],
            [37,40,39,36,34,24,23,18,17],
            [0,38,33,35,21,22,19,20,0],
            [0,0,32,31,27,28,26,0,0],
            [0,0,0,29,30,25,0,0,0]]
        )
        self.dnc_fpga_mask = numpy.array([
            [0,0,0,5,5,6,0,0,0],
            [0,0,5,2,6,6,6,0,0],
            [0,4,4,5,1,1,1,7,0],
            [4,4,2,2,2,1,7,7,7],
            [11,11,11,3,3,0,0,8,8],
            [0,11,3,3,0,0,8,8,0],
            [0,0,10,10,9,9,9,0,0],
            [0,0,0,10,10,9,0,0,0]]
        )

        for y in range(8)  :
            for x in range(9) :
                self.scene_backdrop_item_list.append(itemDNCBackdrop())
                self.scene_backdrop_item_list[-1].setImage(self.dnc_use_mask[y][x])
                self.scene_backdrop_item_list[-1].setPos(QtCore.QPointF(x*102,y*102))
                self.Scene.addItem(self.scene_backdrop_item_list[-1])

        self.scene_rectangle = self.sceneRect()
        self.SetCenter(QtCore.QPointF(self.scene_rectangle.width()/2,self.scene_rectangle.height()/2))
        
    def populateWaferViewDNCs(self,database,wafer_id) :
        self.db = database
        self.wafer_id = wafer_id

        dnc_collection = self.db.DNC
        dncs_used = self.statistics.GetDNCUsedOnWafer(self.wafer_id)
        for y in range(8)  :
            for x in range(9) :
                if self.dnc_use_mask[y][x] == 1 :
                    self.scene_selectable_item_list.append(itemDNCSelectable())
                    self.scene_selectable_item_list[-1].setPos(QtCore.QPointF(x*102,y*102))
                    tooltipstring = "DNC("+str(x)+","+str(y)+")\nID: "+str(self.dnc_id_mask[y][x])
                    self.scene_selectable_item_list[-1].setToolTip(tooltipstring)
                    self.scene_selectable_item_list[-1].setLogicalId(self.dnc_id_mask[y][x])
                    
                    dnc = dnc_collection.find_one({"reticleId":int(self.dnc_id_mask[y][x]), "parent_fpga":int(self.dnc_fpga_mask[y][x]) , "parent_wafer":int(self.wafer_id)})
                    
                    for key, value in dnc.iteritems() :
                        if key == 'available' :
                            if value == True :
                                self.scene_selectable_item_list[-1].setStatus(AVAILABLE)
                                for key, value in dnc.iteritems() :
                                    if key == 'locked' :
                                        if value == True :
                                            self.scene_selectable_item_list[-1].setStatus(LOCKED)
                                for dnc_used in dncs_used :
                                    if dnc_used == self.dnc_id_mask[y][x] :
                                        self.scene_selectable_item_list[-1].setStatus(SELECTED_MAPPER)

                    self.Scene.addItem(self.scene_selectable_item_list[-1])

        self.scene_rectangle = self.sceneRect()
        self.SetCenter(QtCore.QPointF(self.scene_rectangle.width()/2,self.scene_rectangle.height()/2))

    def mousePressEvent(self, event) :
        if event.button() == QtCore.Qt.LeftButton :
            item = self.itemAt(event.pos())
            self.emit(QtCore.SIGNAL("itemSelected"),DNCTREEITEMTYPE,self.wafer_id,item.getLogicalId())
            super(viewWaferAvailabilityDNCs, self).mousePressEvent(event)

    def treeSelectionHandler(self, item, column) :
        '''
        handler to find an DNC item 
        in the scene via its type and logical id
        
        @param item item in the HMF tree
        @param column column in the HMF tree table
        
        '''
        if item.type() == DNCTREEITEMTYPE and int(item.text(1)) == self.wafer_id:
                for selectable_item in self.scene_selectable_item_list :
                    if selectable_item.getLogicalId() == int(item.text(0)) :
                        super(viewWaferAvailabilityDNCs, self)._selector(selectable_item)
                        self.parent().setCurrentWidget(self)

"""

 graphics view for HICANN array
 displaying the availability
 info from the database

"""
class viewWaferAvailabilityHICANNs(viewWafer) :
    
    def __init__(self,statistics,parent=None) :
        viewWafer.__init__(self)
        
        self.statistics = statistics
         
        # 36x18 mask encoding the location
        # of the HICANNs:
        #
        # 0 - empty, 
        # 1 - not accessible,
        # 2 - accessible
        #
        self.hicann_use_mask = numpy.array([
        [0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,1,1,1,1,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,1,1,1,1,0,0,0,0,0,0,0,0],
        [0,0,0,0,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1,1,1,1,0,0,0,0],
        [0,0,0,0,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1,1,1,1,0,0,0,0],
        [0,0,0,0,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,0,0,0,0],
        [0,0,0,0,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,0,0,0,0],
        [2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2],
        [2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2],
        [2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2],
        [2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2],
        [0,0,0,0,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,0,0,0,0],
        [0,0,0,0,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,0,0,0,0],
        [0,0,0,0,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1,1,1,1,0,0,0,0],
        [0,0,0,0,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1,1,1,1,0,0,0,0],
        [0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,1,1,1,1,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,1,1,1,1,0,0,0,0,0,0,0,0]]
        )
        
        for y in range(2*8)  :
            for x in range(4*9) :
                self.scene_backdrop_item_list.append(itemHICANNBackdrop())
                self.scene_backdrop_item_list[-1].setImage(self.hicann_use_mask[y][x])
                self.scene_backdrop_item_list[-1].setPos(QtCore.QPointF(x*50,y*100))
                self.Scene.addItem(self.scene_backdrop_item_list[-1])
        
        # reticle outlines
        for y in range(8)  :
            for x in range(9) :
                self.scene_backdrop_item_list.append(itemReticleBackdrop())
                self.scene_backdrop_item_list[-1].setPos(QtCore.QPointF(x*200,y*200))
                self.Scene.addItem(self.scene_backdrop_item_list[-1])


    def populateWaferViewHICANNs(self,database,wafer_id) :
        
        self.db = database
        self.wafer_id = wafer_id
        
        self.config_id = 0
        hicann_collection = self.db.HICANN
        
        hicanns_used = self.statistics.GetHicannIdsUsedOnWafer(self.wafer_id)
        hicanns_specified = self.statistics.GetHicannIdsSpecifiedOnWafer(self.wafer_id)
        
        for y in range(2*8)  :
            for x in range(4*9) :
                if self.hicann_use_mask[y][x] == 2 :
                    self.scene_selectable_item_list.append(itemHICANNSelectable())
                    self.scene_selectable_item_list[-1].setPos(QtCore.QPointF(x*50,y*100))
                    tooltipstring = "HICANN("+str(x)+","+str(y)+")\nID: "+str(self.config_id)
                    self.scene_selectable_item_list[-1].setToolTip(tooltipstring)
                    self.scene_selectable_item_list[-1].setLogicalId(self.config_id)

                    hicann = hicann_collection.find_one({"configId":int(self.config_id), "parent_wafer": int(self.wafer_id)})
                    for key, value in hicann.iteritems() :
                        if key == 'available' :
                            if value == True :
                                self.scene_selectable_item_list[-1].setStatus(AVAILABLE)
                                for key, value in hicann.iteritems() :
                                    if key == 'locked' :
                                        if value == True :
                                            self.scene_selectable_item_list[-1].setStatus(LOCKED)
                        for hicann_used in hicanns_used :
                            if hicann_used == self.config_id :
                                    self.scene_selectable_item_list[-1].setStatus(SELECTED_MAPPER)
                        for hicann_spec in hicanns_specified :
                            if hicann_spec == self.config_id :
                                    self.scene_selectable_item_list[-1].setStatus(SELECTED_USER)
                    self.config_id += 1
                    self.Scene.addItem(self.scene_selectable_item_list[-1])

        self.scene_rectangle = self.sceneRect()
        self.SetCenter(QtCore.QPointF(self.scene_rectangle.width()/2,self.scene_rectangle.height()/2))
   
    def mousePressEvent(self, event) :
        if event.button() == QtCore.Qt.LeftButton :
            if self.itemAt(event.pos()) :
                item = self.itemAt(event.pos())
                self.emit(QtCore.SIGNAL("itemSelected"),HICANNTREEITEMTYPE,self.wafer_id,item.getLogicalId())
                super(viewWaferAvailabilityHICANNs, self).mousePressEvent(event)

# TODO -- ME: this might super go
    def treeSelectionHandler(self, item, column) :
        '''
        handler to find an HICANN item 
        in the scene via its type and logical id
        
        @param item item in the HMF tree
        @param column column in the HMF tree table
        
        '''
        if item.type() == HICANNTREEITEMTYPE and int(item.text(1)) == self.wafer_id:
                for selectable_item in self.scene_selectable_item_list :
                    if selectable_item.getLogicalId() == int(item.text(0)) :
                        super(viewWaferAvailabilityHICANNs, self)._selector(selectable_item)
                        self.parent().setCurrentWidget(self)

 
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

 Post Processing

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

"""

 graphics view for FPGA array
 displaying the utilisation

 items that where available for mapping display the average utilisation and 
 are selectable
 
"""
class viewWaferUtilisationFPGAs(viewWafer) :

 def __init__(self,statistics,wafer_id=0,parent=None) :
        '''
        draw a wafer array of DNCs and display their
        average utilisation, the database is not required,
        the necessary info is aquired from the datamodels
        via the statistics 
        
        @param statistics from there the utilisation values are aquired 
        @param wafer_id the id for the current wafer 
        '''
        
        viewWafer.__init__(self)
        
        self.statistics = statistics
        self.wafer_id = wafer_id

        # mask encoding the location
        # of the FPGAs on the PCB grid
        # 0 - empty, 
        # 1 - front,
        # 2 - back
        self.fpga_use_mask  = numpy.array([
            [0,1,2,1,0],
            [1,0,0,0,1],
            [2,0,0,0,2],
            [1,0,0,0,1],
            [0,1,2,1,0]]
        )
        # mask encoding the FPGA id in the system
        self.fpga_id_mask  = numpy.array([
            [0,9,2,8,0],
            [10,0,0,0,7],
            [3,0,0,0,1],
            [11,0,0,0,6],
            [0,4,0,5,0]]
        )

        for y in range(5)  :
            for x in range(5) :
                self.scene_backdrop_item_list.append(itemFPGABackdrop())
                self.scene_backdrop_item_list[-1].setImage(self.fpga_use_mask[y][x])
                self.scene_backdrop_item_list[-1].setPos(QtCore.QPointF(x*102,y*102))
                self.Scene.addItem(self.scene_backdrop_item_list[-1])

        self.scene_rectangle = self.sceneRect()
        self.SetCenter(QtCore.QPointF(self.scene_rectangle.width()/2,self.scene_rectangle.height()/2))

        fpgas_used = self.statistics.GetFPGAUsedOnWafer(self.wafer_id)
        
        for y in range(5) :
            for x in range(5) :
                if self.fpga_use_mask[y][x] == 2 or self.fpga_use_mask[y][x] == 1 :
                    
                    for fpga in fpgas_used : 
                        if fpga == self.fpga_id_mask[y][x] :
                            self.scene_selectable_item_list.append(coloredFPGABlocktItem())
                            self.scene_selectable_item_list[-1].setPos(QtCore.QPointF(x*102,y*102))
                            fpga_utilisation = self.statistics.GetFPGAUtilisation(self.wafer_id, int(fpga))
                            if fpga_utilisation < 0.0 :
                                print "InteractiveMapping: WARNING FPGA utilisation could not be determined for FPGA with id: ",int(fpga)
                            self.tooltipstring = "FPGA ID: " +str(fpga) +"\n Utilisation: "+str(fpga_utilisation)
                            self.scene_selectable_item_list[-1].setToolTip(self.tooltipstring)
                            self.scene_selectable_item_list[-1].set_utilisation_color(fpga_utilisation)
                            self.Scene.addItem(self.scene_selectable_item_list[-1])

"""

 graphics view for DNC array
 displaying the utilisation

 items that where available for mapping display the average utilisation and 
 are selectable
 
"""
class viewWaferUtilisationDNCs(viewWafer) :
    
    def __init__(self,statistics,wafer_id=0,parent=None) :
        '''
        draw a wafer array of DNCs and display their
        average utilisation, the database is not required,
        the necessary info is aquired from the datamodels
        via the statistics 
        
        @param statistics from there the utilisation values are aquired 
        @param wafer_id the id for the current wafer
        '''
        
        viewWafer.__init__(self)
        
        self.statistics = statistics
        self.wafer_id = wafer_id

        # mask encoding the location
        # 
        # of the DNCs
        # 0 - empty, 
        # 1 - not empty
        self.dnc_use_mask = numpy.array([
            [0,0,0,1,1,1,0,0,0],
            [0,0,1,1,1,1,1,0,0],
            [0,1,1,1,1,1,1,1,0],
            [1,1,1,1,1,1,1,1,1],
            [1,1,1,1,1,1,1,1,1],
            [0,1,1,1,1,1,1,1,0],
            [0,0,1,1,1,1,1,0,0],
            [0,0,0,1,1,1,0,0,0]]
        )
        self.dnc_id_mask = numpy.array([
            [0,0,0,1,4,5,0,0,0],
            [0,0,2,45,6,7,8,0,0],
            [0,44,43,3,11,11,10,14,0],
            [41,42,47,48,46,9,15,16,13],
            [37,40,39,36,34,24,23,18,17],
            [0,38,33,35,21,22,19,20,0],
            [0,0,32,31,27,28,26,0,0],
            [0,0,0,29,30,25,0,0,0]]
        )
        self.dnc_fpga_mask = numpy.array([
            [0,0,0,5,5,6,0,0,0],
            [0,0,5,2,6,6,6,0,0],
            [0,4,4,5,1,1,1,7,0],
            [4,4,2,2,2,1,7,7,7],
            [11,11,11,3,3,0,0,8,8],
            [0,11,3,3,0,0,8,8,0],
            [0,0,10,10,9,9,9,0,0],
            [0,0,0,10,10,9,0,0,0]]
        )

        for y in range(8)  :
            for x in range(9) :
                self.scene_backdrop_item_list.append(itemDNCBackdrop())
                self.scene_backdrop_item_list[-1].setImage(self.dnc_use_mask[y][x])
                self.scene_backdrop_item_list[-1].setPos(QtCore.QPointF(x*102,y*102))
                self.Scene.addItem(self.scene_backdrop_item_list[-1])

        self.available_dncs = self.statistics.GetDNCUsedOnWafer(wafer_id)
        for y in range(8)  :
            for x in range(9) :
                if self.dnc_use_mask[y][x] == 1 :
                    for dnc in self.available_dncs :
                        if dnc == self.dnc_id_mask[y][x] :
                            self.scene_selectable_item_list.append(coloredDNCBlocktItem())
                            self.scene_selectable_item_list[-1].setPos(QtCore.QPointF(x*102,y*102))
                            dnc_utilisation = self.statistics.GetDNCUtilisation(self.wafer_id, int(dnc))
                            if dnc_utilisation < 0.0 :
                                print "InteractiveMapping: WARNING DNC utilisation could not be determined for DNC with id: ",int(dnc)
                            self.tooltipstring = "DNC ID: " +str(dnc) +"\n Utilisation: "+str(dnc_utilisation)
                            self.scene_selectable_item_list[-1].setToolTip(self.tooltipstring)
                            self.scene_selectable_item_list[-1].set_utilisation_color(dnc_utilisation)
                            self.Scene.addItem(self.scene_selectable_item_list[-1])

        self.scene_rectangle = self.sceneRect()
        self.SetCenter(QtCore.QPointF(self.scene_rectangle.width()/2,self.scene_rectangle.height()/2))


"""

 graphics view for HICANN array
 displaying the utilisation

 items that where available for mapping display the average utilisation and 
 are selectable to update a detailed view
 
"""
class viewWaferUtilisationHICANNs(viewWafer) :
    
    def __init__(self,statistics,wafer_id=0,parent=None) :
        '''
        draw a wafer array of HICANNs and display their
        average utilisation, the database is not required,
        the necessary info is aquired from the datamodels
        via the statistics 
        
        @param statistics from there the utilisation values are aquired 
        '''
        
        viewWafer.__init__(self)
        
        self.statistics = statistics
        self.wafer_id = wafer_id
        
        # 36x18 mask encoding the location
        # of the HICANNs:
        #
        # 0 - empty, 
        # 1 - not accessible,
        # 2 - accessible
        #
        self.hicann_use_mask = numpy.array([
            [0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,1,1,1,1,0,0,0,0,0,0,0,0],
            [0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,1,1,1,1,0,0,0,0,0,0,0,0],
            [0,0,0,0,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1,1,1,1,0,0,0,0],
            [0,0,0,0,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1,1,1,1,0,0,0,0],
            [0,0,0,0,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,0,0,0,0],
            [0,0,0,0,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,0,0,0,0],
            [2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2],
            [2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2],
            [2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2],
            [2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2],
            [0,0,0,0,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,0,0,0,0],
            [0,0,0,0,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,0,0,0,0],
            [0,0,0,0,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1,1,1,1,0,0,0,0],
            [0,0,0,0,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1,1,1,1,0,0,0,0],
            [0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,1,1,1,1,0,0,0,0,0,0,0,0],
            [0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,1,1,1,1,0,0,0,0,0,0,0,0]]
        )

        for y in range(2*8)  :
            for x in range(4*9) :
                self.scene_backdrop_item_list.append(itemHICANNBackdrop())
                self.scene_backdrop_item_list[-1].setImage(self.hicann_use_mask[y][x])
                self.scene_backdrop_item_list[-1].setPos(QtCore.QPointF(x*60,y*110))
                self.Scene.addItem(self.scene_backdrop_item_list[-1])

        self.available_hicanns = self.statistics.GetHicannIdsUsedOnWafer(wafer_id)
        self.config_id = 0
        for y in range(2*8) :
            for x in range(4*9) :
                if self.hicann_use_mask[y][x] == 2 :
  
                    for hicann in self.available_hicanns :
                        if hicann == self.config_id :
                            self.scene_selectable_item_list.append(coloredHICANNBlocktItem())
                            self.scene_selectable_item_list[-1].setPos(QtCore.QPointF(x*60,y*110))
                            hicann_utilisation = self.statistics.GetHicannUtilisation(self.wafer_id, int(hicann))
                            if hicann_utilisation < 0.0 :
                                print "InteractiveMapping: WARNING HICANN utilisation could not be determined for HICANN with id: ",int(hicann)
                            self.tooltipstring = "HICANN ID: " +str(hicann) +"\n Utilisation: "+str(hicann_utilisation)
                            self.scene_selectable_item_list[-1].setToolTip(self.tooltipstring)
                            self.scene_selectable_item_list[-1].set_utilisation_color(hicann_utilisation)
                            self.Scene.addItem(self.scene_selectable_item_list[-1])
                    self.config_id += 1
    
        self.scene_rectangle = self.sceneRect()
        self.SetCenter(QtCore.QPointF(self.scene_rectangle.width()/2,self.scene_rectangle.height()/2))

'''
    def mousePressEvent(self, event) :
        self.setCursor(QtCore.Qt.ClosedHandCursor)
        
        # if a HICANN is selected by "left-click" and it is an available hicann
        # then it is signaled that the detailed HICANN view should 
        # update its information according to the config_id
        if event.button() == QtCore.Qt.LeftButton :
            self.item_selected = None
            item = self.itemAt(event.pos())
            if item != None :
                config_id = item.toolTip()
                for hicann in self.available_hicanns :
                    if int(config_id) == hicann :
                        self.emit(QtCore.SIGNAL("request_update_detailed_view"),int(config_id))
                        self.item_selected = item
                        self.item_selected.set_mouse_pressed()

    def mouseReleaseEvent(self, event) :
        self.setCursor(QtCore.Qt.OpenHandCursor)
        
        if self.item_selected :
            self.item_selected.set_mouse_released()
            self.item_selected = None
'''

"""

 graphics view for a HICANN 
 displaying the utilisation of the building blocks

 items are not selectable
 
"""
class viewHICANNUtilisationDetailed(QtGui.QGraphicsView) :

    def __init__(self,statistics,wafer_id=0,parent=None) :
        '''
        draw the outline of the HICANNs functional
        components
        
        @param statistics from there the utilisation values are aquired 
        '''
        
        QtGui.QGraphicsView.__init__(self)
        
        self.statistics = statistics
        self.config_id = -1
       
        self.Scene = QtGui.QGraphicsScene(self)
        self.setScene(self.Scene)
        #self.setCursor(QtCore.Qt.OpenHandCursor)
       
        self.synapse_up = coloredBlocktItem()
        self.synapse_up.setRect(QtCore.QRectF(QtCore.QPointF(100,0),QtCore.QPointF(800,550)))
        self.synapse_up.setToolTip("Synapse block upper half")
        self.Scene.addItem(self.synapse_up)
        self.synapse_down = coloredBlocktItem()
        self.synapse_down.setRect(QtCore.QRectF(QtCore.QPointF(100,600),QtCore.QPointF(800,1150)))
        self.synapse_down.setToolTip("Synapse block lower half")
        self.Scene.addItem(self.synapse_down)

        self.syndriver_up_left = coloredBlocktItem()
        self.syndriver_up_left.setRect(QtCore.QRectF(QtCore.QPointF(100,0),QtCore.QPointF(200,550)))
        self.syndriver_up_left.setToolTip("Synapse Driver upper left")
        self.Scene.addItem(self.syndriver_up_left)
        self.syndriver_up_right = coloredBlocktItem()
        self.syndriver_up_right.setRect(QtCore.QRectF(QtCore.QPointF(700,0),QtCore.QPointF(800,550)))
        self.syndriver_up_right.setToolTip("Synapse Driver upper right")
        self.Scene.addItem(self.syndriver_up_right)
        self.syndriver_down_left = coloredBlocktItem()
        self.syndriver_down_left.setRect(QtCore.QRectF(QtCore.QPointF(100,600),QtCore.QPointF(200,1150)))
        self.syndriver_down_left.setToolTip("Synapse Driver lower left")
        self.Scene.addItem(self.syndriver_down_left)
        self.syndriver_down_right = coloredBlocktItem()
        self.syndriver_down_right.setRect(QtCore.QRectF(QtCore.QPointF(700,600),QtCore.QPointF(800,1150)))
        self.syndriver_down_right.setToolTip("Synapse Driver lower right")
        self.Scene.addItem(self.syndriver_down_right)
        
        self.denmem_up = coloredBlocktItem()
        self.denmem_up.setRect(QtCore.QRectF(QtCore.QPointF(100,450),QtCore.QPointF(800,550)))
        self.denmem_up.setToolTip("Dendritic membranes upper half")
        self.Scene.addItem(self.denmem_up)
        self.denmem_down = coloredBlocktItem()
        self.denmem_down.setRect(QtCore.QRectF(QtCore.QPointF(100,600),QtCore.QPointF(800,700)))
        self.denmem_down.setToolTip("Dendritic membranes lower half")
        self.Scene.addItem(self.denmem_down)
        
        self.l1_bus_vertical_left = coloredBlocktItem()
        self.l1_bus_vertical_left.setRect(QtCore.QRectF(QtCore.QPointF(0,0),QtCore.QPointF(150,1150)))
        self.l1_bus_vertical_left.setToolTip("L1 bus vertical left")
        self.Scene.addItem(self.l1_bus_vertical_left)
        self.l1_bus_vertical_right = coloredBlocktItem()
        self.l1_bus_vertical_right.setRect(QtCore.QRectF(QtCore.QPointF(750,0),QtCore.QPointF(900,1150)))
        self.l1_bus_vertical_right.setToolTip("L1 bus vertical right")
        self.Scene.addItem(self.l1_bus_vertical_right)
        self.l1_bus_horizontal = coloredBlocktItem()
        self.l1_bus_horizontal.setRect(QtCore.QRectF(QtCore.QPointF(0,500),QtCore.QPointF(900,650)))
        self.l1_bus_horizontal.setToolTip("L1 bus horizontal")
        self.Scene.addItem(self.l1_bus_horizontal)
        
        self.crossbar_left = coloredBlocktItem()
        self.crossbar_left.setRect(QtCore.QRectF(QtCore.QPointF(0,500),QtCore.QPointF(150,650)))
        self.crossbar_left.setToolTip("Crossbar left")
        self.Scene.addItem(self.crossbar_left)
        self.crossbar_right = coloredBlocktItem()
        self.crossbar_right.setRect(QtCore.QRectF(QtCore.QPointF(750,500),QtCore.QPointF(900,650)))
        self.crossbar_right.setToolTip("Crossbar right")
        self.Scene.addItem(self.crossbar_right)

        self.selectswitch_up_left = coloredBlocktItem()
        self.selectswitch_up_left.setRect(QtCore.QRectF(QtCore.QPointF(0,150),QtCore.QPointF(150,400)))
        self.selectswitch_up_left.setToolTip("Select-Switch upper left")
        self.Scene.addItem(self.selectswitch_up_left)
        self.selectswitch_up_right = coloredBlocktItem()
        self.selectswitch_up_right.setRect(QtCore.QRectF(QtCore.QPointF(750,150),QtCore.QPointF(900,400)))
        self.selectswitch_up_right.setToolTip("Select-Switch upper right")
        self.Scene.addItem(self.selectswitch_up_right)
        self.selectswitch_down_left = coloredBlocktItem()
        self.selectswitch_down_left.setRect(QtCore.QRectF(QtCore.QPointF(0,750),QtCore.QPointF(150,1000)))
        self.selectswitch_down_left.setToolTip("Select-Switch lower left")
        self.Scene.addItem(self.selectswitch_down_left)
        self.selectswitch_down_right = coloredBlocktItem()
        self.selectswitch_down_right.setRect(QtCore.QRectF(QtCore.QPointF(750,750),QtCore.QPointF(900,1000)))
        self.selectswitch_down_right.setToolTip("Select-Switch lower right")
        self.Scene.addItem(self.selectswitch_down_right)

        self.repeater_mid_left = coloredBlocktItem()
        self.repeater_mid_left.setRect(QtCore.QRectF(QtCore.QPointF(0,500),QtCore.QPointF(50,650)))
        self.repeater_mid_left.setToolTip("Repeater mid left")
        self.Scene.addItem(self.repeater_mid_left)
        self.repeater_mid_right = coloredBlocktItem()
        self.repeater_mid_right.setRect(QtCore.QRectF(QtCore.QPointF(850,500),QtCore.QPointF(900,650)))
        self.repeater_mid_right.setToolTip("Repeater mid right")
        self.Scene.addItem(self.repeater_mid_right)
        self.repeater_up_left = coloredBlocktItem()
        self.repeater_up_left.setRect(QtCore.QRectF(QtCore.QPointF(0,0),QtCore.QPointF(150,50)))
        self.repeater_up_left.setToolTip("Repeater upper left")
        self.Scene.addItem(self.repeater_up_left)
        self.repeater_up_right = coloredBlocktItem()
        self.repeater_up_right.setRect(QtCore.QRectF(QtCore.QPointF(750,0),QtCore.QPointF(900,50)))
        self.repeater_up_right.setToolTip("Repeater upper right")
        self.Scene.addItem(self.repeater_up_right)
        self.repeater_down_left = coloredBlocktItem()
        self.repeater_down_left.setRect(QtCore.QRectF(QtCore.QPointF(0,1100),QtCore.QPointF(150,1150)))
        self.repeater_down_left.setToolTip("Repeater lower left")
        self.Scene.addItem(self.repeater_down_left)
        self.repeater_down_right = coloredBlocktItem()
        self.repeater_down_right.setRect(QtCore.QRectF(QtCore.QPointF(750,1100),QtCore.QPointF(900,1150)))
        self.repeater_down_right.setToolTip("Repeater lower right")
        self.Scene.addItem(self.repeater_down_right)
        
        self.hicann_label = QtGui.QGraphicsTextItem("HICANN("+QtCore.QString(str(self.config_id))+")")
        self.hicann_label.setScale(3.0)
        self.hicann_label.setPos(QtCore.QPointF(300,550))
        self.Scene.addItem(self.hicann_label)
       
        self.setSceneRect(-50, -50, 900, 1200)
        self.scale(0.5,0.5)

    def update_detailed_view(self,config_id):
        '''
        slot to updated the detailed view according to 
        the utilisation information of
        the HICANN given by config_id
        
        @param config_id via the configuration id the utilisation values are
                         aquired from the statistics object 
 
        depending on the implementation of the statistics objects methods
        to retrieve statistics the update may take a while ...
        
        TODO: have the update in a separate thread and show a clock while
              updating
        '''
        self.config_id = config_id
        self.hicann_label.setPlainText("HICANN("+QtCore.QString(str(self.config_id))+")")
        
        # for each element of the detailed view request 
        # the utilisation info from the statistics object
        # and the elements color accordingly
        
        self.synapse_up.set_utilisation(0.20)
        self.synapse_down.set_utilisation(0.45)
        
        self.syndriver_up_left.set_utilisation(0.36)
        self.syndriver_up_right.set_utilisation(0.6)
        self.syndriver_down_left.set_utilisation(0.74)
        self.syndriver_down_right.set_utilisation(0.22)
        
        self.denmem_up.set_utilisation(self.statistics.hicannDenmemUtilisationUp(int(self.config_id)))
        self.denmem_down.set_utilisation(0.5)
        
        self.l1_bus_vertical_left.set_utilisation(0.04)
        self.l1_bus_vertical_right.set_utilisation(0.5)
        self.l1_bus_horizontal.set_utilisation(0.9)
        
        self.crossbar_left.set_utilisation(0.1)
        self.crossbar_right.set_utilisation(0.1)

        self.selectswitch_up_left.set_utilisation(0.4)
        self.selectswitch_up_right.set_utilisation(0.34)
        self.selectswitch_down_left.set_utilisation(0.67)
        self.selectswitch_down_right.set_utilisation(0.45)

        self.repeater_mid_left.set_utilisation(0.6)
        self.repeater_mid_right.set_utilisation(0.53)
        self.repeater_up_left.set_utilisation(0.23)
        self.repeater_up_right.set_utilisation(0.13)
        self.repeater_down_left.set_utilisation(0.45)
        self.repeater_down_right.set_utilisation(0.8)
