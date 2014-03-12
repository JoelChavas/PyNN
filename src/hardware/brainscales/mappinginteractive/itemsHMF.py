"""

 HMF graphic view items, i.e. FPGA, DNC, HICANN

"""

from PyQt4 import QtCore
from PyQt4 import QtGui

import os

MAPPINGINTERACTIVEPATH = os.environ['SYMAP2IC_PATH']+'/components/pynnhw/src/hardware/brainscales/mappinginteractive/'

"""
a block element as base element of the utilisation
map which holds the precise utilisation
value and determines a color according 
to the utilisation.
from green not utilised
to red fully utilised
"""

class coloredBlocktItem(QtGui.QGraphicsRectItem) :

    def __init__(self,parent=None) :
        QtGui.QGraphicsRectItem.__init__(self)
        self.setAcceptHoverEvents(True)
        self.outline_color = QtGui.QColor()
        self.filling_color = QtGui.QColor()
        self._set_named_color("#000000")
        self.selected = None
        self.original_color = QtGui.QColor()
        
    def _set_named_color(self,color) :
        # the outline is solid
        self.outline_color.setNamedColor(color)
        self.setPen(QtGui.QPen(self.outline_color,1,QtCore.Qt.SolidLine))
        # the filling is half transparent
        self.filling_color.setNamedColor(color)
        self.filling_color.setAlpha(100)
        self.setBrush(QtGui.QBrush(self.filling_color))

    def _set_hsl_color(self,h) :
        # the outline is solid
        self.outline_color.setHsl(h,255,155)
        self.setPen(QtGui.QPen(self.outline_color,1,QtCore.Qt.SolidLine))
        # the filling is half transparent
        self.filling_color.setHsl(h,255,155)
        self.filling_color.setAlpha(255)
        self.setBrush(QtGui.QBrush(self.filling_color))
        
    # utilisation color from green over yellow to red
    # HSL model S-155 L-255 H 90 -> 0
    def set_utilisation_color(self,colorparam):
        self.colorparam = colorparam
        # choose the color according to the param
        if self.colorparam > 0.9 : # (0.9<u<=1.0)
            self._set_hsl_color(0)
        elif self.colorparam > 0.8 : # (0.8<u<=0.9)
            self._set_hsl_color(10)
        elif self.colorparam > 0.7 : # (0.7<u<=0.8)
            self._set_hsl_color(20)
        elif self.colorparam > 0.6: # (0.6<u<=0.7)
            self._set_hsl_color(30)
        elif self.colorparam > 0.5: # (0.5<u<=0.6)
            self._set_hsl_color(40)
        elif self.colorparam > 0.4: # (0.4<u<=0.5)
            self._set_hsl_color(50)
        elif self.colorparam > 0.3: # (0.3<u<=0.4)
            self._set_hsl_color(60)
        elif self.colorparam > 0.2: # (0.2<u<=0.3)
            self._set_hsl_color(70)
        elif self.colorparam > 0.1: # (0.1<u<=0.2)
            self._set_hsl_color(80)
        elif self.colorparam >= 0.0: # (0.0<=u<=0.1)
            self._set_hsl_color(90)
        else :
            self.set_grey()

    def set_grey(self) :
        self._set_named_color("#BDBDBD")

    def set_white(self) :
        self._set_named_color("#FFFFFF")
        
    def set_blue(self) :
        self._set_named_color("#B4CDCD")
    
    def toggleSelected(self) :
        if not self.selected :
            self.original_color.setNamedColor(self.outline_color.name())
            self._set_named_color(self.original_color.darker(factor=300).name())
            self.selected = True 
        else: 
            self._set_named_color(self.original_color.name())
            self.selected = False
            
    def set_mouse_pressed(self) :
        self.original_color = self.outline_color
        self._set_named_color(self.original_color.darker(factor=300).name())
        
    def set_mouse_released(self) :
        self._set_named_color(self.original_color.name())
        self.original_color = None

class coloredFPGABlocktItem(coloredBlocktItem) :
    def __init__(self,parent=None) :
        coloredBlocktItem.__init__(self)
        self.setRect(QtCore.QRectF(QtCore.QPointF(0,0),QtCore.QPointF(100,100)))

class coloredDNCBlocktItem(coloredBlocktItem) :
    def __init__(self,parent=None) :
        coloredBlocktItem.__init__(self)
        self.setRect(QtCore.QRectF(QtCore.QPointF(0,0),QtCore.QPointF(100,100)))

class coloredHICANNBlocktItem(coloredBlocktItem) :
    def __init__(self,parent=None) :
        coloredBlocktItem.__init__(self)
        self.setRect(QtCore.QRectF(QtCore.QPointF(0,0),QtCore.QPointF(50,100)))
 
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

  BACKDROPS

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

"""

 an backdrop item which is not selectable

"""

class itemBackdrop(QtGui.QGraphicsPixmapItem) :
       
    def __init__(self, parent=None) :
        
        QtGui.QGraphicsPixmapItem.__init__(self)
        self.setAcceptHoverEvents(False)
        self.setAcceptedMouseButtons(QtCore.Qt.NoButton)

    '''
    no way to make the scene item not selectable
    so have this dummy function instead
    '''
        
    def toggleSelected(self) :
        return
    def getLogicalId(self) :
        return -1

"""

 an FPGA backdrop item which is not selectable

"""

FPGA_ITEM_EMPTY = 0
FPGA_ITEM_TOP = 1
FPGA_ITEM_BOTTOM = 2

class itemFPGABackdrop(itemBackdrop) :
    
    def __init__(self, parent=None) :
        itemBackdrop.__init__(self)

    def setImage(self,selector) :
        if selector == FPGA_ITEM_EMPTY :
            self.setPixmap(QtGui.QPixmap(MAPPINGINTERACTIVEPATH+'pics/fpga_empty_tile.png'))
        elif selector == FPGA_ITEM_TOP or selector == FPGA_ITEM_BOTTOM :
            self.setPixmap(QtGui.QPixmap(MAPPINGINTERACTIVEPATH+'pics/fpga_tile.png'))
        else :
            self.setPixmap(QtGui.QPixmap(MAPPINGINTERACTIVEPATH+'pics/fpga_empty_tile.png'))

DNC_ITEM_EMPTY = 0
DNC_ITEM_TOP = 1

class itemDNCBackdrop(itemBackdrop) :
    
    def __init__(self, parent=None) :
        itemBackdrop.__init__(self)

    def setImage(self,selector) :
        if selector == DNC_ITEM_EMPTY :
            self.setPixmap(QtGui.QPixmap(MAPPINGINTERACTIVEPATH+'pics/dnc_empty_tile.png'))
        elif selector == DNC_ITEM_TOP :
            self.setPixmap(QtGui.QPixmap(MAPPINGINTERACTIVEPATH+'pics/dnc_tile.png'))
        else :
            self.setPixmap(QtGui.QPixmap(MAPPINGINTERACTIVEPATH+'pics/dnc_empty_tile.png'))

HICANN_ITEM_EMPTY = 0
HICANN_ITEM_UNREACHABLE = 1
HICANN_ITEM_TOP = 2

class itemHICANNBackdrop(itemBackdrop) :
    
    def __init__(self, parent=None) :
        itemBackdrop.__init__(self)

    def setImage(self,selector) :
        if selector == HICANN_ITEM_EMPTY :
            self.setPixmap(QtGui.QPixmap(MAPPINGINTERACTIVEPATH+'pics/hicann_empty_tile.png'))
        elif selector == HICANN_ITEM_UNREACHABLE :
            self.setPixmap(QtGui.QPixmap(MAPPINGINTERACTIVEPATH+'pics/hicann_inaccessible_tile.png'))
        elif selector == HICANN_ITEM_TOP :
            self.setPixmap(QtGui.QPixmap(MAPPINGINTERACTIVEPATH+'pics/hicann_tile.png'))
        else :
            self.setPixmap(QtGui.QPixmap(MAPPINGINTERACTIVEPATH+'pics/hicann_empty_tile.png'))

class itemReticleBackdrop(QtGui.QGraphicsRectItem) :
    
    def __init__(self, parent=None) :
        QtGui.QGraphicsRectItem.__init__(self)
        self.setAcceptHoverEvents(False)
        self.setAcceptedMouseButtons(QtCore.Qt.NoButton)

        self.setRect(QtCore.QRectF(QtCore.QPointF(0,0),QtCore.QPointF(200,200)))
        
        self.outline_color = QtGui.QColor()
        self.filling_color = QtGui.QColor()
        # the outline is solid
        self.outline_color.setNamedColor("#000000")
        self.setPen(QtGui.QPen(self.outline_color,3,QtCore.Qt.SolidLine))
        # the filling is  transparent
        self.filling_color.setAlpha(0)
        self.setBrush(QtGui.QBrush(self.filling_color))
        
    def toggleSelected(self) :
        return
    def getLogicalId(self) :
        return -1


"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

  SELECTABLES

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

"""

 a selectable scene rectangle item 
 
"""
LOCKED = 0
AVAILABLE = 1
SELECTED_USER = 2
SELECTED_MAPPER = 3

class itemSelectable(QtGui.QGraphicsRectItem) :
       
    def __init__(self, parent=None) :
        QtGui.QGraphicsRectItem.__init__(self)
        self.setAcceptHoverEvents(True)
        self.outline_color = QtGui.QColor()
        self.filling_color = QtGui.QColor()
        self._set_named_color("#000000")
        
        self.selected = False
        self.original_color = QtGui.QColor()
        
    def setStatus(self,status) :
        '''
        0 - red -- locked
        1 - green -- available but not allocated for mapping green
        2 - blue -- preselected by the user
        3 - yellow --allocated by the mapping process
        '''
        if status == LOCKED :
            self._set_named_color("#FF0000")
        elif status == AVAILABLE :
            self._set_named_color("#00FF00")
        elif status == SELECTED_USER :
            self._set_named_color("#0000FF")
        elif status == SELECTED_MAPPER :
            self._set_named_color("#FFFF00")
        else :
            self._set_named_color("#000000")

    def _set_named_color(self,color) :
        # the outline is solid
        self.outline_color.setNamedColor(color)
        self.setPen(QtGui.QPen(self.outline_color,0,QtCore.Qt.SolidLine))
        # the filling is half transparent
        self.filling_color.setNamedColor(color)
        self.filling_color.setAlpha(100)
        self.setBrush(QtGui.QBrush(self.filling_color))
    
    def setLogicalId(self,logical_id):
        self.logical_id = logical_id
        
    def getLogicalId(self):
        return self.logical_id
        
    def toggleSelected(self) :
        if not self.selected :
            self.original_color.setNamedColor(self.outline_color.name())
            self._set_named_color("#FFA500")
            self.selected = True
        else: 
            self._set_named_color(self.original_color.name())
            self.selected = False

"""

 selectable FPGA item

"""

class itemFPGASelectable(itemSelectable) :
       
    def __init__(self, parent=None) :
        itemSelectable.__init__(self)
        self.setRect(QtCore.QRectF(QtCore.QPointF(0,0),QtCore.QPointF(100,100)))

"""

 selectable DNC item

"""

class itemDNCSelectable(itemSelectable) :
       
    def __init__(self, parent=None) :
        itemSelectable.__init__(self)
        self.setRect(QtCore.QRectF(QtCore.QPointF(0,0),QtCore.QPointF(100,100)))

"""

 selectable HICANN item

"""

class itemHICANNSelectable(itemSelectable) :
       
    def __init__(self, parent=None) :
        itemSelectable.__init__(self)
        self.setRect(QtCore.QRectF(QtCore.QPointF(0,0),QtCore.QPointF(50,100)))

