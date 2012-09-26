"""
A module to fix tiff files from the AFS database system 
Based on the TIF 6.0 Specification
http://partners.adobe.com/public/developer/en/tiff/TIFF6.pdf
"""

from struct import unpack, calcsize, pack
from os import path
import binascii
import struct

__author__ = 'Aron Vietti'
__date__ = "$November 03, 2010$"
__all__ = ["read_header"]

# Magic Numbers from the Specification

# Image header variables
BYTE_ORDER_POSITION = 0 # Location of the Byte order
BYTE_ORDER_VALUE = {'II':'little endian', 'MM':'big endian'}
IDENT_POSITION = 2 # Location of the Tiff identifier
IDENTIFIER = 42 # An arbitrary but carefully chosen number (42) that
                # further identifies the file as a TIFF file.

IFD_OFFSET_POSITION = 4 # Location of the offset for the first 
                        # Image File Directory aka IFD.

# IFD variables
DIRECTORY_ENTRY_LENGTH = 12
IFD_COUNT_LENGTH = 2
TYPES = {1:('BYTE','B', 1), 2:('ASCII','c', 1), 3:('SHORT','H', 2),\
         4:('LONG','L', 4), 5:('RATIONAL','LL', 8), 6:('SBYTE','b', 1),\
         7:('UNDEFINED','c', 1), 8:('SSHORT','h', 2), 9:('SLONG','l', 4),\
         10:('SRATIONAL','ll', 8), 11:('FLOAT','f', 4), 12:('DOUBLE','d', 8)}

#Directory lists for tiff_info
HEADER = ('File Name', 'File Size', 'Byte Order')
IFD_INFO = ('Position', 'Number of Directories', 'Directory Entry ')
DIRECTORIES = ('Offset', 'Tag', 'Type', 'Count', 'Value Offset', 'Value')
def read_tiff(f_input):
    """Read a TIFF File and return the header information
    
    Make sure this is a TIFF file by determining the byte order and
    checking for the IDENTIFIER. Return False if it does not meet the
    specification requirements.
    
    Find the the offset for the fist Image File Directory AKA IFD and
    move to that position in the file, then check all the Directory
    Entries for the jeader information.
    
    Each Directory Entry is 12 bytes and the Tag is the first 2 bytes, 
    the Value starts at byte 8.
    """
    #To hold all of the information collected from the headers
    #First entry is file and header info, the each ifd
    tiff_info = []
    
    #Size of file, in case last ifd is not terminated properly
    file_size = path.getsize(f_input)
    
    try:
        f=open(f_input, 'rb')
    except IOError as (errno, e):
        if errno == 22:
            return False
        print f_input
        print e
        
    
    #Check if the file is a valid TIFF
    byte_order = get_byte_order(f)
    if byte_order == False:
        return False
    f.seek(IDENT_POSITION)
    if read_binary(2, f, byte_order) != IDENTIFIER:
        return False    
    #At this point we know we are dealing with a Tiff
    header_info = {}
    header_info['File Name'] = path.basename(f_input)
    header_info['File Size'] = file_size
    header_info['Byte Order'] = byte_order
    
    tiff_info.append(header_info)
    
    # Check for the tags needed
    next_offset = -1
    while next_offset < file_size:
        offset, ifd_info = read_ifd(f, byte_order, next_offset)
        next_offset = offset
        tiff_info.append(ifd_info)
    return tiff_info
        

def read_ifd(f, byte_order, offset=-1):
    #dictionary for storing the ifd information
    ifd_info = {}
    # Get the offset for the IFD
    if offset == -1:
        f.seek(IFD_OFFSET_POSITION)
        IFD = read_binary(4, f, byte_order)
    else:
        IFD = offset
    f.seek(IFD)
    directory_count = read_binary(2, f, byte_order)
    
    ifd_info['Position'] = IFD
    ifd_info['Number of Directories'] = directory_count
    
    dir_start = IFD+IFD_COUNT_LENGTH #starting position for Directory Entries
    count = 0
    while count < directory_count:
        #dictionary for this directory
        dir_info = {}
        dir_info['Offset'] = dir_start+(count*DIRECTORY_ENTRY_LENGTH)
        f.seek(dir_start+(count*DIRECTORY_ENTRY_LENGTH))
        
        tag = read_binary(2, f, byte_order)
        dir_info['Tag'] = tag
        
        type = read_binary(2, f, byte_order)
        dir_info['Type'] = type
        
        value_count = read_binary(4, f, byte_order)
        dir_info['Count'] = value_count
        if calcsize(str(value_count)+TYPES[type][1]) <= 4:
            dir_info['Value Offset'] = f.tell()
            values = read_binary(4, f, byte_order)
            dir_info['Value'] = values
        else:
            value_offset = read_binary(4, f, byte_order)
            f.seek(value_offset)
            values = read_binary(TYPES[type][1], f, byte_order, value_count)
            dir_info['Value Offset'] = value_offset
            try:     
                dir_info['Value'] = "".join(values)
            except TypeError:
                dir_info['Value'] = values
                  
        ifd_info['Directory Entry '+str(count)] = dir_info
        count += 1
        
    f.seek(dir_start+(count*DIRECTORY_ENTRY_LENGTH))
    offset = read_binary(4, f, byte_order)
    try:
        offset = check_offset(f, offset, byte_order, dir_start+(count*DIRECTORY_ENTRY_LENGTH))
    except struct.error: pass
    return offset, ifd_info
def check_offset(f, offset, byte_order, dir_end):
    f.seek(offset+IFD_COUNT_LENGTH)
    test = read_binary(2, f, byte_order)
    tags = (269, 254)
    types = (2, 4)
    check = 0
    if test in tags: 
        check = 1 
        return offset
    while check == 0:
        while test not in tags:
            test = read_binary(2, f, byte_order)
        type = read_binary(2, f, byte_order)
        if type in types:
            check = 1
    offset = f.tell()-6
    return offset
            
def get_byte_order(f):
    """ Determine the Byte Order
    The first two bytes of the file contain the byte order.
    The Character that struct needs is returned, or False if
    the Byte Order is missing.
    """
    f.seek(BYTE_ORDER_POSITION)
    order = f.read(2)
    try:
        if BYTE_ORDER_VALUE[order] == 'little endian':
            return '<'
        elif BYTE_ORDER_VALUE[order] == 'big endian':
            return '>'
        else:
            return False
    except KeyError:
        return False

def read_binary(size, f, byte_order='=', count=1):
    """
    Function to simplify using unpack from the struct module to read
    binary data. The dictionary formats is based on the Characters
    in the struct model documentation. 
    """
    formats = {1:'c', 2:'H', 4:'i', 8:'d'}
    if type(size) == int:
        s = formats[size]
    else:
        s = size
    data_length = calcsize(byte_order+str(count)+s)
    data = unpack(byte_order+str(count)+s, f.read(data_length))
        
    if len(data) <= 1:
        return data[0]
    else:
        return data
    
def print_tiff_info(tiff_info):
    count = 0
    for each in tiff_info:
        if count == 0:
            for item in HEADER:
                print '%s: %s' % (str(item),str(each[item]))
        else:
            print 'IFD %i' % count 
            for item in IFD_INFO:
                if item != 'Directory Entry ':
                    print '\t%s: %s' % (str(item),str(each[item]))
                else:
                    dir_count = 0
                    while dir_count < each['Number of Directories']:
                        current_dir = str(item+str(dir_count))
                        dir = each[current_dir]
                        print '\t%s' % current_dir
                        for dir_item in DIRECTORIES:
                            print '\t\t%s: %s' %(str(dir_item) ,str(dir[dir_item]))
                        dir_count += 1                            
        count += 1
def split_tiff(tiff_info, input, output):
    input_f = open(input, 'rb')
    #get variable from the header
    filename = tiff_info[0]['File Name']
    filesize = tiff_info[0]['File Size']
    byte_order = tiff_info[0]['Byte Order']
    header = input_f.read(8)
    file_list = []
    #we start at one to skip the header info
    
    count = 1
    global image_location
    global new_image_location
    global image_length
    global image_location_offset
    global data_end
    ifd_count = len(tiff_info)
    while count < ifd_count:
        data_end = 0
        dir_count = 0
        ifd = tiff_info[count]
        while dir_count < ifd['Number of Directories']:
            if tiff_info[count]['Directory Entry '+str(dir_count)]['Tag'] == 269:       
                filename = tiff_info[count]['Directory Entry '+str(dir_count)]['Value'].split(',')[2].replace('\0', '')
            dir_count += 1    
        output_f = open(path.join(output, filename+'.tif'), 'wb')
        file_list.append(path.join(output, filename+'.tif'))
        output_f.write(header)
        output_f.write(pack('H', ifd['Number of Directories']))
        
        dir_count = 0
        while dir_count < ifd['Number of Directories']:
            cur_dir = 'Directory Entry %i' %dir_count
            dir = ifd[cur_dir]
            input_f.seek(dir['Offset'])
            output_f.seek(8+2+(dir_count)*12)
            output_f.write(input_f.read(12))
            dir_end = (8+2+(ifd['Number of Directories'])*12)+4
            if data_end == 0:
                data_end = dir_end
            #to keep track of bytes written after the directory
            if dir['Tag'] == 273:
                output_f.seek(-4, 1)
                image_location = dir['Value']
                image_location_offset = output_f.tell()
                
            elif dir['Tag'] == 279:
                image_length = dir['Value'] 
            elif dir['Tag'] == 262:
                output_f.seek(-4, 1)
                output_f.write('\x00\x00\x00\x00')
            
            else:
                if dir['Value Offset'] != dir['Offset']+8:
                    input_f.seek(dir['Value Offset'])
                    output_f.seek(-4, 1)
                    new_offset = data_end
                    output_f.write(pack('L', new_offset))
                    value_length = TYPES[dir['Type']][2]*dir['Count']
                    output_f.seek(new_offset)
                    data_end = data_end + TYPES[dir['Type']][2]*dir['Count'] 
                    output_f.write(input_f.read(value_length))
                if dir_count == ifd['Number of Directories']-1:
                    #wite the value of the next IFD
                    #output_f.write(input_f.read(4))
                    #Always zero when spliting
                    output_f.seek(dir['Offset']+12)
                    output_f.write('\x00\x00\x00\x00')
                    try:
                        new_image_location = data_end+1
                        output_f.seek(image_location_offset)
                        output_f.write(pack('L', new_image_location))
                        output_f.seek(new_image_location)
                        input_f.seek(image_location)
                        output_f.write(input_f.read(image_length))
                    except NameError: pass
                
                    
            dir_count += 1
        output_f.close()                    
        count += 1
    return file_list
def get_image(): pass 

def fix_ifd(tiff_info):
    new_info = []
    new_info.append(tiff_info[0])
    imagedescription = {}
    make = {}
    software = {}
    datetime = {}
    #skip the header
    count = 1
    while count < len(tiff_info):
        if count == 1:
            dir_count = 0
            while tiff_info[count]['Number of Directories'] > dir_count:
                if tiff_info[count]['Directory Entry '+str(dir_count)]['Tag'] == 270:
                    imagedescription = tiff_info[count]['Directory Entry '+str(dir_count)]
                elif tiff_info[count]['Directory Entry '+str(dir_count)]['Tag'] == 271:
                    make = tiff_info[count]['Directory Entry '+str(dir_count)]
                elif tiff_info[count]['Directory Entry '+str(dir_count)]['Tag'] == 305:
                    software = tiff_info[count]['Directory Entry '+str(dir_count)]
                elif tiff_info[count]['Directory Entry '+str(dir_count)]['Tag'] == 306:
                    datetime = tiff_info[count]['Directory Entry '+str(dir_count)]
                dir_count += 1
        elif tiff_info[count]['Directory Entry 0']['Tag'] == 254:
            sort_list = []
            sort_lookup = {}
            dir_count = 0
            while tiff_info[count-1]['Number of Directories'] > dir_count:
                tag = tiff_info[count-1]['Directory Entry '+str(dir_count)]['Tag']
                sort_list.append(tag)
                if tiff_info[count-1]['Directory Entry '+str(dir_count)]['Tag'] == 270:
                    sort_lookup[tag] = imagedescription
                elif tiff_info[count-1]['Directory Entry '+str(dir_count)]['Tag'] == 271:
                    sort_lookup[tag] = make
                elif tiff_info[count-1]['Directory Entry '+str(dir_count)]['Tag'] == 305:
                    sort_lookup[tag] = software
                elif tiff_info[count-1]['Directory Entry '+str(dir_count)]['Tag'] == 306:
                    sort_lookup[tag] = datetime 
                else:
                    sort_lookup[tag] = tiff_info[count-1]['Directory Entry '+str(dir_count)]
                dir_count += 1
            dir_count = 0
            while tiff_info[count]['Number of Directories'] > dir_count:
                tag = tiff_info[count]['Directory Entry '+str(dir_count)]['Tag']
                sort_list.append(tag)
                if tiff_info[count]['Directory Entry '+str(dir_count)]['Tag'] == 270:
                    sort_lookup[tag] = imagedescription
                elif tiff_info[count]['Directory Entry '+str(dir_count)]['Tag'] == 271:
                    sort_lookup[tag] = make
                elif tiff_info[count]['Directory Entry '+str(dir_count)]['Tag'] == 305:
                    sort_lookup[tag] = software
                elif tiff_info[count]['Directory Entry '+str(dir_count)]['Tag'] == 306:
                    sort_lookup[tag] = datetime
                else:
                    sort_lookup[tag] = tiff_info[count]['Directory Entry '+str(dir_count)]
                
                dir_count += 1
            new_ifd = {}
            new_ifd['Position'] = tiff_info[count-1]['Position']
            new_ifd['Number of Directories'] = len(sort_list)
            sort_list.sort()
            tag_count = 0
            while tag_count < len(sort_list):
                new_ifd['Directory Entry '+str(tag_count)] = sort_lookup[sort_list[tag_count]]
                tag_count += 1
            new_info.append(new_ifd)
        count += 1
    return new_info
        
if __name__ == "__main__":
    f = "/home/aron/workspace/Western Integrated conversion/test2/10192010/FILES/CAPS044.I00"
    output = "/home/aron/workspace/Western Integrated conversion/"
    tiff_info = read_tiff(f)
    tiff_info = fix_ifd(tiff_info)
    print_tiff_info(tiff_info)
    split_tiff(tiff_info, f, output)
    