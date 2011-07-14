#!/usr/bin/env python
# encoding: utf-8
"""
pyarb.py

Created by Klaus-Michael Aye on 2011-07-12.
Copyright (c) 2011 Klaus-Michael Aye. All rights reserved.
"""
from traits.api import HasPrivateTraits, Button, List, Str, File, Property, Unicode
from traitsui.api import View, Item, HGroup, TabularEditor, DirectoryEditor
from traitsui.tabular_adapter import TabularAdapter
from traitsui.menu import OKButton, CancelButton
import os
import struct
import numpy as np

class WFMFile(file):
    """class to handle waveform ('wfm') files of the AWG615 arbitrary wave generator.
    Format description (from the AWG615 manual)
    <Waveform File>::=<Header><Body>[<Trailer>]
    where:
    <Header>::=MAGIC<space>1000<CR><LF>
    <Body>::=#<Num_digits><Num_bytes><Data(1)><Data(2)>...<Data(n)>
        <Num_digits> is the number of digits in <Num_bytes>.
        <Num_bytes> is the byte count of the data that follows.
        <Data(n)>::=<Waveform><Marker>
            <Waveform> is the single precision floating–point number of 4–byte 
            Little Endian format specified in IEEE488.2. The full scale of the
            D/A converter of the waveform generator corresponds to -1.0 to 1.0.
            <Marker> is one byte of marker data. The bit 0 (LSB) and bit 1 
            represent markers 1 and 2, respectively.
    <Trailer>::=CLOCK<space><Clock><CR><LF> 
        <Clock> is the value of the sample clock in ASCII.
    """
    header = 'MAGIC 1000\r\n'
    def __init__(self, *args, **kwargs):
        """
        Initialization is the same as a normal file object
        %s""" % file.__doc__
        file.__init__(self, *args, **kwargs)
    def read_data(self):
        header = self.read(12)
        self.read(1) # read and dump the '#'
        num_digits = int(self.read(1))
        num_bytes = int(self.read(num_digits))
        print("Found {0} data points".format(num_bytes/5))
        data = []
        counter = 0
        while counter < num_bytes:
            bunch = self.read(5)
            # bunch[4] is the marker byte of no interest for data
            # taking the first value [0] of the result because unpack returns
            # a 1-element tuple
            data.append(struct.unpack('<f',bunch[:4])[0])
            counter += 5
        self.clock = self.read().split()[1]
        return data
    def write_data(self,data,clock):
        self.write(self.header)
        num_bytes = 5*len(data)
        num_digits = len(str(num_bytes))
        self.write('#{0}{1}'.format(num_digits,num_bytes))
        for item in data:
            # 0 for the not used markers, they were also all 0 in some files from AWG
            self.write(struct.pack('<fb',item,0))
        self.write('CLOCK {0:0.10e}\n'.format(clock))

class PulseTxtFile(file):
    """class to read in the data in ascii format"""
    def __init__(self, *args, **kwargs):
        """
        Initialization is the same as a normal file object
        %s""" % file.__doc__
        file.__init__(self, *args, **kwargs)
    def read_data(self):
        """returns a tuple with 3 elemens: (clock_rate, size, data_array)"""
        # all the magic: cut off '#',strip off EOL chars, split to get
        # part after (i.e. [1]) the '='
        clock = float(self.readline()[1:].strip().split('=')[1])
        size = int(self.readline()[1:].strip().split('=')[1])
        str = self.read()
        data = np.fromstring(str,dtype=np.double,count=size,sep='\r\n')
        return (clock,size,data)
    

class MultiSelectAdapter ( TabularAdapter ):
    columns = [ ( 'Value', 'value' ) ]
    value_text = Property
    def _get_value_text ( self ):
        return self.item

class Converter ( HasPrivateTraits ):
    homeDir = File(editor = DirectoryEditor(),
        desc="Folder from where to pick files to convert",
        label="Source Folder")
    choices = List(Unicode, desc="A list of filenames that should be converted.")
    selected = List(Unicode, desc="The list of output filenames.")
    statusText = Str
    fire_convert = Button('Convert')
    fire_reload = Button('Reload Directory')
                  
    view = View(Item('homeDir'),
                HGroup(
                    Item('choices',
                         show_label = False,
                         editor = TabularEditor(
                            show_titles = False,
                            selected = 'selected',
                            editable = False,
                            multi_select = True,
                            adapter = MultiSelectAdapter())
                    ),
                    Item ('selected',
                          show_label = False,
                          editor = TabularEditor(
                            show_titles = False,
                            editable = False,
                            adapter = MultiSelectAdapter())
                    )
                ),
                Item('statusText', style='custom',show_label=False),
                HGroup(
                    Item('fire_reload',show_label=False),
                    Item('fire_convert',show_label=False,width=0.5),
                ),
                buttons = [OKButton,CancelButton],
                resizable = True,
                title = 'Pick folder and select files to convert',
                width = 700, height = 700,
            )

    def _fire_convert_fired(self):
        self.convert()
    
    def _update_choices(self):
        try:
            listing = os.listdir(self.homeDir)
        except OSError:
            return
        for item in listing[:]:
            if item.startswith('.'):
                listing.remove(item)
        self.choices = listing
        
    def _fire_reload_fired(self):
        self._update_choices()
        self._feedback('Reloaded directory, found {0} entries.'.format(len(self.choices)))
    
    def _homeDir_changed(self,new):
        if not os.path.isdir(new):
            self._feedback("Somehow this is not a directory. Try again.")
            return
        self._update_choices()
        self._feedback("Set directory to: {0}, found {1} entries".format(new,
            len(self.choices)))

    def _feedback(self, txt):
        print(txt)
        self.statusText += txt+'\n'

    def convert(self):
        for fname in self.selected:
            pulseTxtFile = PulseTxtFile(fname,'r')
            clock, size, data = pulseTxtFile.read_data()
            pulseTxtFile.close()
            fnameRoot = fname[:-4]
            newFileName = fnameRoot + '.wfm'
            wfm = WFMFile(newFileName,'wb')
            wfm.write_data(data,clock)
            wfm.close()
            self._feedback("Created {0}".format(newFileName))
        self._fire_reload_fired()
        

if __name__ == '__main__':
    conv = Converter(statusText="""
Pick a directory to work in.
A listing of the files will be shown in the left part of the window. 
Select all files for conversion, they will be listed on the right side.
Press 'Convert' to do the conversion, the new files will be placed in
the same directory. 
No error handling is done so far: 
If you convert a.csv and a.txt, only 1 file will make it to a.wfm 
(the latter in alphabet).\n""")
    conv.configure_traits()
