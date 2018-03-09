#!/usr/bin/python

# scan a wave file for dropouts - repeated samples for more than thresh consecutive samples

import wave 
import struct
import numpy as np
import sys

fname="ph1995-06-13d1t07_raw.wav"
#thresh= 100
#thresh= 50
#thresh= 25

CHUNK=4096
#  1024 0m56.249s
#  2048 0m54.811s
#  4096 0m54.317s
#  8192 0m55.491s
# 16384 0m56.624s

class DAT_Fix:
    """
    " scan a wav file from a DAT transfer for "drop-outs"
    " or sections where successive samples are equal for a count
    " of more than thresh samples
    """
    def __init__(self):
        first_left=None
        last_left=None
        count_left=0
        first_right=None
        last_right=None
        count_right=0
    # END Dropout_Scan.init()
        
    def sample_to_time( self, sample ):
        sample_rate = self.framerate
        seconds = sample // sample_rate
        samples = sample  % sample_rate
        minutes = seconds // 60
        seconds = seconds  % 60
        timestr = "{0:09d} {1:03d}m{2:02d}s+{3:05d}samp".format( sample, minutes, seconds, samples)
        return timestr

    def init_file(self):
        self.left_state  = { "first":None, "last":None, "count":0, "prev":0, "channel":"L" }
        self.right_state = { "first":None, "last":None, "count":0, "prev":0, "channel":"R" }
        self.error = 0
    # END Dropout_Scan.init_file()

    def analyze_frame( self, sample, state ):
        thresh= 100
        #print("A: "+fname+" {0:s} {1:s}".format( self.sample_to_time( self.frame_num), state["channel"] ))
        for i in range( len(sample) ):
            if sample[i] == state["prev"]:
                if 0 == state["count"]:
                    state["first"] ="{0:s} {1:5d}".format( self.sample_to_time( i+ self.frame_num), sample[i] )
                    state["count"] = 1
                else:
                    state["count"] += 1
                    if state["count"] > thresh:
                        state["last"] = "{0:s} {1:5d}".format( self.sample_to_time( i + self.frame_num ), sample[i])
            else: # not equal
                if state["first"] is not None and state["last"] is not None:
                    if self.error == 0:
                        print("") # force newline
                        self.error = 1
                    print ( state["channel"] + " Start " + state["first"] + " End " + state["last"] +
                            " Dur " + self.sample_to_time( state["count"] ))
                state["first"]=None
                state["last"]=None
                state["count"] = 0
                state["prev"] = sample[i]
    # END Dropout_Scan.analyze_frame()
        
    def analyze_frame_last( self, state ):
        if state["first"] is not None and state["last"] is not None:
            if self.error == 0:
                print("") # force newline
                self.error = 1
            print ( state["channel"] + " Start " + state["first"] + " End " + state["last"] +
                    " Dur " + self.sample_to_time( state["count"] ))
    # END Dropout_Scan.analyze_frame_last()
        
    
    def scan_file( self, fname ):
        # TODO - return count of dropout/duplicate frames
        # as a score for evaluting relative quality of different files 
        if fname is None:
            raise ValueError

        wav = wave.open (fname, "r")

        (self.nchannels, self.sampwidth, self.framerate,
         self.nframes, self.comptype, self.compname)     = wav.getparams ()

        #print("O: "+fname+" {0:d} channels {1:d} frames".format(self.nchannels, self.nframes) )
        
        print("A: "+fname, end='', flush=True)
        self.init_file()

        # ceil( nframes / CHUNK)
        # thanks to https://stackoverflow.com/questions/14822184/is-there-a-ceiling-equivalent-of-operator-in-python
        # ceil ( a /b ) == -( -a // b)
        num_chunks = -( -self.nframes // CHUNK)
        
        self.frame_num = 0
        
        for chunk_num in range( num_chunks ):

            # handle possibly odd sized last chunk
            if self.frame_num + CHUNK > self.nframes:
                chunk_size = self.nframes - chunk_num*CHUNK
            else:
                chunk_size = CHUNK

            # read the next chunk
            frame = wav.readframes ( chunk_size )
            out = struct.unpack_from ( "%dh" % self.nchannels * chunk_size, frame )

            # Convert 2 channels to numpy arrays and analyze for drop-outs
            if self.nchannels == 2:
                left_samples  = np.array (list ( out[0::2] ))
                right_samples = np.array (list ( out[1::2] ))
                self.analyze_frame( left_samples,  self.left_state )
                self.analyze_frame( right_samples, self.right_state )
            else:
                left_samples  = np.array (list ( out[0::2] ))
                self.analyze_frame( left_samples, self.left_state )
            self.frame_num += chunk_size

        # catch "hanging" dropout at end of file
        self.analyze_frame_last( self.left_state )
        self.analyze_frame_last( self.right_state )

        # close file
        wav.close()

        if self.error == 0:
            print(" OK")
        else:
            print( "Done" )
    # END Dropout_Scan.scan_file()

    def get_file_info( self, file ):
        #print( "I: " + file["name"] )
        wav = wave.open ( file["name"], "r")
        #with wave.open ( file["name"], "r") as wav:

        (nchannels, sampwidth, framerate,
         nframes, comptype, compname)     = wav.getparams ()

        file["nchannels"] = nchannels
        file["sampwidth"] = sampwidth
        file["framerate"] = framerate
        file["nframes"]   = nframes
        file["comptype"]  = comptype
        file["compname"]  = compname
        
        wav.close()
    # END DAT_Fix.get_file_info()
    
    def print_file_info( self, file ):
        print( "P: " + file["name"] )
        print("  nchannels:{0:d} sampwidth:{1:d} framerate:{2:d} nframes:{3:d} comptype:{4:s} compname:{5:s}\n".format(
            file["nchannels"], file["sampwidth"], file["framerate"],
            file["nframes"], file["comptype"], file["compname"] )
        )

    # END DAT_Fix.print_file_info()

    def get_leader_length( self, file ):
        """
        " Scan for an arbitrarily long sequence of zero sample
        " at the start of a file, so that it can be eliminated
        "
        " inputs:
        "   file{} - dictionary with info on the wav file from the dat transfer
        "   file[ "name" ] - the name of the file
        "   file[ "nchannels" ] - number of audio channels per frame in the file
        "   file[ "sampwidth" ] - number of bytes per channel 
        "   file[ "sampwidth" ] - number of bytes per channel 
        "   file[ "framerate" ] - number of frames per second 
        "   file[ "nframes" ]   - total number of frames in the file 
        "
        " outputs:
        "   file[ "leader_length" ] - count of initial zero sample in the file
        "
        " assumes sampwidth == 2 ???
        """
        if file[ "name" ] is None:
            raise ValueError

        # local copies of file parameters
        filename  = file[ "name" ]
        nchannels = file[ "nchannels" ]
        #sampwidth = file[ "sampwidth" ]
        nframes   = file[ "nframes" ]
        
        if nchannels != 2:
            print( "Can't handle anything other than stereo yet")
            raise ValueError

        wav = wave.open ( filename, "r")

        # ceil( nframes / CHUNK)
        # thanks to https://stackoverflow.com/questions/14822184/is-there-a-ceiling-equivalent-of-operator-in-python
        # ceil ( a /b ) == -( -a // b)
        num_chunks = -( -file[ "nframes" ] // CHUNK )
        
        lead_frames = 0
        done = 0
        
        for chunk_num in range( num_chunks ):

            # handle possibly odd sized last chunk
            if lead_frames + CHUNK > nframes:
                chunk_size = nframes - chunk_num*CHUNK
            else:
                chunk_size = CHUNK

            # read the next chunk
            chunk = wav.readframes ( chunk_size )
            out = struct.unpack_from ( "%dh" % nchannels * chunk_size, chunk )

            # Convert 2 channels to numpy arrays and analyze for drop-outs
            left_samples  = np.array (list ( out[0::2] ))
            right_samples = np.array (list ( out[1::2] ))

            for i in range( len( left_samples ) ):
                if left_samples[i] != 0 or right_samples[i] != 0:
                    done = 1
                    break
                else:
                    lead_frames += 1
                
            print( "{0:s}  leader: {1:d} net frames:{3:d}".format(filename, lead_frames, end='\r', flush=True)
            if done :
                break

        print( "\n{0:s}  total frames:{1:d} leader: {2:d} net frames:{3:d}".format(
            filename, nframes, lead_frames, nframes - lead_frames ), end='\r', flush=True)
        # close file
        wav.close()
        print()
        file[ "leader_length" ] = lead_frames
                   
    # END DAT_Fix.get_leader_length()

    
    def dropout_score_mem( self, file ):
        """
        " calculate the number of duplicated samples in a file
        " 
        " Some duplicates are natural in a sound file,
        " but DAT tape dropouts tend to present as runs of 
        " duplicate samples 25, 50, 100+ samples long
        " 
        " counting how many duplicate samples are present in the file
        " is a metric of how many dropouts are present and how long they are.
        " If a comparison is made between multiple transfers of the same 
        " DAT material, the number natural duplicates should be the same
        " assuming the leader and trailer have been trimmed off. The
        " remaining differences are likely due to dropouts, and the premise
        " is that a lower dropout score is a better source for the transfer
        "
        " inputs:
        "   file - a file info dictionary as generated by by get_file_info() function and get_leader_length()
        "          it is assumed that the entire file fits in memory
        "          TODO - what is the performance hit due to scanning by chunks instead of using memory buffer
        "
        " outputs:
        "   dropout_score - tuple (l, r) count of number of duplicate adjacent samples 
        """
        # local copies of file parameters
        filename    = file[ "name" ]
        nframes     = file[ "nframes" ]
        lead_frames = file[ "leader_length" ]

        #sampwidth = file_list[0][ "sampwidth" ]
        #framerate = file_list[0][ "framerate" ]

        wav = wave.open ( filename, "r")


        # ceil( nframes / CHUNK)
        # thanks to https://stackoverflow.com/questions/14822184/is-there-a-ceiling-equivalent-of-operator-in-python
        # ceil ( a /b ) == -( -a // b)
        nframes = (nframes - lead_frames)
        num_chunks = -( -nframes // CHUNK )
        
        nchannels = 2

        
        # fast forward through lead_frames
        wav.readframes ( lead_frames )

        # read all the remaining data
        # note: currently no mechanism to trim trailer
        data = wav.readframes( nframes )

        out = struct.unpack_from ( "%dh" % nchannels * nframes, data )

        # Convert 2 channels to numpy arrays and analyze for drop-outs
        left  = np.array (list ( out[0::2] ))
        right = np.array (list ( out[1::2] ))

        # shift one instance of the array by 1 sample, and subtract
        # to find adjacent duplicate samples
        left_delta  = left [1:] - left [:-1]
        right_delta = right[1:] - right[:-1]

        # adapted from https://stackoverflow.com/questions/2900084/counting-positive-integer-elements-in-a-list-with-python-list-comprehensions
        # makes a list of the zero element, then length of the list is count of the zero elements
        left_score  = len( [x for x in left_data  if x == 0] )
        right_score = len( [x for x in right_data if x == 0] )

        print( "dropout score: {0:s} frames:{1:d} L:{2:d} R:{3:d} total:{4:d}".format(
            filename, nframes, left_score, right_score))
        
        # close file
        wav.close()

        return (left_score, right_score)
    # END DAT_Fix.dropout_score_mem()
    
    def dropout_score_chunk( self, file ):
        """
        " calculate the number of duplicated samples in a file
        " 
        " Some duplicates are natural in a sound file,
        " but DAT tape dropouts tend to present as runs of 
        " duplicate samples 25, 50, 100+ samples long
        " 
        " counting how many duplicate samples are present in the file
        " is a metric of how many dropouts are present and how long they are.
        " If a comparison is made between multiple transfers of the same 
        " DAT material, the number natural duplicates should be the same
        " assuming the leader and trailer have been trimmed off. The
        " remaining differences are likely due to dropouts, and the premise
        " is that a lower dropout score is a better source for the transfer
        "
        " this version is better for large files, it doesn't try to load the
        " entire file into memory, rather processes it in chunks. This is
        " slower, but will work on large files
        "
        " inputs:
        "   file - a file info dictionary as generated by by get_file_info() function and get_leader_length()
        "
        " outputs:
        "   dropout_score - tuple (l, r) count of number of duplicate adjacent samples 
        """
        # local copies of file parameters
        filename    = file[ "name" ]
        nframes     = file[ "nframes" ]
        lead_frames = file[ "leader_length" ]

        #sampwidth = file_list[0][ "sampwidth" ]
        framerate = file_list[0][ "framerate" ]
        self.framerate = framerate
        
        wav = wave.open ( filename, "r")


        # ceil( nframes / CHUNK)
        # thanks to https://stackoverflow.com/questions/14822184/is-there-a-ceiling-equivalent-of-operator-in-python
        # ceil ( a /b ) == -( -a // b)
        nframes = (nframes - lead_frames)
        num_chunks = -( -nframes // CHUNK )
        
        nchannels = 2

        
        # fast forward through lead_frames
        wav.readframes ( lead_frames )

        # pre-scan initialization
        frame_num = 0
        prev_l = 0
        prev_r = 0

        left_count = 0
        right_count = 0

        for chunk_num in range( num_chunks ):

            # handle possibly odd sized last chunk
            if frame_num + CHUNK > nframes:
                chunk_size = nframes - chunk_num*CHUNK
            else:
                chunk_size = CHUNK

            # read the next chunk
            chunk = wav.readframes ( chunk_size )
            out = struct.unpack_from ( "%dh" % nchannels * chunk_size, chunk )

            # Convert 2 channels to numpy arrays and analyze for drop-outs
            left  = np.array (list ( out[0::2] ))
            right = np.array (list ( out[1::2] ))

            #chunk_corrected = np.array[ zip( left_m, right_m ) ]
            for l, r  in zip (left, right ):
                if l == prev_l:
                    left_count += 1
                if r == prev_r:
                    right_count += 1
                    
            prev_l = l
            prev_r = r
            
            frame_num += chunk_size
            print( "C:{0:08d} F:{1:s}\tL:{2:09d} R:{3:09d} total:{4:d} frac:{5:f}".format(
                chunk_num, self.sample_to_time( frame_num ),
                left_count, right_count,
                (left_count+right_count), (left_count+right_count) / (2.0*frame_num) ),
                   end='\r', flush=True)

        print("\n")
        print( "dropout score: {0:s} frames:{1:d} L:{2:d} R:{3:d} total:{4:d} frac:{5:f}".format(
            filename, nframes, left_count, right_count,
            (left_count+right_count), (left_count+right_count) / (2.0*nframes) ))
        
        # close file
        wav.close()

        return (left_count, right_count)
    # END DAT_Fix.dropout_score_chunk()

    def dropout_score( self, file ):
        return self.dropout_score_chunk( file )
        
    def median_3( self, file_list ):
        """
        " take three copies of a file
        " and use a median filter to eliminate dropouts where possible
        "
        " Note: this is fairly fast and shows some improvement, 
        " but can sometimes propagate errors
        """
        # local copies of file parameters
        filename_1    = file_list[0][ "name" ]
        filename_2    = file_list[1][ "name" ]
        filename_3    = file_list[2][ "name" ]
        nframes_1     = file_list[0][ "nframes" ]
        nframes_2     = file_list[1][ "nframes" ]
        nframes_3     = file_list[2][ "nframes" ]
        lead_frames_1 = file_list[0][ "leader_length" ]
        lead_frames_2 = file_list[1][ "leader_length" ]
        lead_frames_3 = file_list[2][ "leader_length" ]

        sampwidth = file_list[0][ "sampwidth" ]
        framerate = file_list[0][ "framerate" ]

        wav_1 = wave.open ( filename_1, "r")
        wav_2 = wave.open ( filename_2, "r")
        wav_3 = wave.open ( filename_3, "r")


        # ceil( nframes / CHUNK)
        # thanks to https://stackoverflow.com/questions/14822184/is-there-a-ceiling-equivalent-of-operator-in-python
        # ceil ( a /b ) == -( -a // b)
        nframes = min( (nframes_1 - lead_frames_1), (nframes_2 - lead_frames_2), (nframes_3 - lead_frames_3) )
        num_chunks = -( -nframes // CHUNK )
        
        #num_chunks_1 = -( -( nframes_1 - lead_frames_1 ) // CHUNK )
        #num_chunks_2 = -( -( nframes_2 - lead_frames_2 ) // CHUNK )
        #num_chunks_3 = -( -( nframes_3 - lead_frames_3 ) // CHUNK )

        #num_chunks = min( num_chunks_1, num_chunks_2, num_chunks_3 )
        
        nchannels = 2

        # prepare the output file
        wav_out = wave.open( "out.wav", 'wb' )
        wav_out.setnchannels( nchannels )
        wav_out.setsampwidth( sampwidth )
        wav_out.setframerate( framerate )
        wav_out.setnframes( nframes )
        
        
        # fast forward through lead_frames
        wav_1.readframes ( lead_frames_1 )
        wav_2.readframes ( lead_frames_2 )
        wav_3.readframes ( lead_frames_3 )

        # scan file for differences
        frame_num = 0
        
        for chunk_num in range( num_chunks ):

            # handle possibly odd sized last chunk
            if frame_num + CHUNK > nframes:
                chunk_size = nframes - chunk_num*CHUNK
            else:
                chunk_size = CHUNK

            # read the next chunk
            chunk = wav_1.readframes ( chunk_size )
            out = struct.unpack_from ( "%dh" % nchannels * chunk_size, chunk )

            # Convert 2 channels to numpy arrays and analyze for drop-outs
            left_1  = np.array (list ( out[0::2] ))
            right_1 = np.array (list ( out[1::2] ))

            chunk = wav_2.readframes ( chunk_size )
            out = struct.unpack_from ( "%dh" % nchannels * chunk_size, chunk )
            left_2  = np.array (list ( out[0::2] ))
            right_2 = np.array (list ( out[1::2] ))

            chunk = wav_3.readframes ( chunk_size )
            out = struct.unpack_from ( "%dh" % nchannels * chunk_size, chunk )
            left_3  = np.array (list ( out[0::2] ))
            right_3 = np.array (list ( out[1::2] ))

            left  = np.array( [left_1,  left_2,  left_3] )
            right = np.array( [right_1, right_2, right_3] )

            # use numpy.median() to find "majority vote" of the three samples
            left_m  = np.median( left,  axis=0)
            right_m = np.median( right, axis=0)

            #chunk_corrected = np.array[ zip( left_m, right_m ) ]
            for (l, r ) in zip (left_m, right_m ):
                wav_out.writeframesraw( struct.pack('<hh', int(l), int(r) ) )
            
            frame_num += chunk_size
            print( "C:{0:08d} F:{1:09d}".format( chunk_num, frame_num ), end='\r', flush=True)

        # close file
        wav_1.close()
        wav_2.close()
        wav_3.close()
        wav_out.close()
    # END DAT_Fix.median_3()


    def do_scan_and_fill_2( self, file_list, thresh=100 ):
        """
        " look for dropouts in file 1 where sample values are duplicated 
        " for more than thresh samples, and then attempt to fill them from
        " another file if there duplicate sample run length is less.
        "
        " This should work well for dropouts where the level is held constant
        " and successive takes yield shorter dropouts or dropouts in different areas.
        "
        " this will not work for noisy dropouts where the value changes rapidly.
        "
        " inputs:
        "    file_list: list of file info dicts provided by get_file_info() function
        "               requires two files
        "               TODO: this reall needs two and only two files, specify directly rather than as a list?
        "    thresh:    optional - specify threshold dropout size to fill
        "
        " outputs:
        "    out.wav:   merged file
        """
        # local copies of file parameters
        filename_master    = file_list[0][ "name" ]
        filename_donor     = file_list[1][ "name" ]

        nframes_master     = file_list[0][ "nframes" ]
        nframes_donor      = file_list[1][ "nframes" ]

        lead_frames_master = file_list[0][ "leader_length" ]
        lead_frames_donor  = file_list[1][ "leader_length" ]

        sampwidth = file_list[0][ "sampwidth" ]
        framerate = file_list[0][ "framerate" ]

        print("dropout threshold: "+str(thresh))
                   
        self.framerate = framerate

        wav_master = wave.open ( filename_master, "r")
        wav_donor  = wave.open ( filename_donor, "r")


        # ceil( nframes / CHUNK)
        # thanks to https://stackoverflow.com/questions/14822184/is-there-a-ceiling-equivalent-of-operator-in-python
        # ceil ( a /b ) == -( -a // b)
        nframes = min( (nframes_master - lead_frames_master), (nframes_master - lead_frames_master) )

        num_chunks = -( -nframes // CHUNK )
        
        nchannels = 2

        # prepare the output file
        wav_out = wave.open( "out.wav", 'wb' )
        wav_out.setnchannels( nchannels )
        wav_out.setsampwidth( sampwidth )
        wav_out.setframerate( framerate )
        wav_out.setnframes( nframes )
        
        # fast forward through lead_frames
        wav_master.readframes ( lead_frames_master )
        wav_donor.readframes (  lead_frames_donor )

        # pre-scan initialization
        frame_num = 0
        prev_l = 0
        dropout_len_l = 0
        master_l_data = []
        donor_l_data = []
        out_l_data = []
        
        prev_r = 0
        dropout_len_r = 0
        donor_r_data = []
        master_r_data = []
        out_r_data = []

        # scan file for differences
        for chunk_num in range( num_chunks ):

            # handle possibly odd sized last chunk
            if frame_num + CHUNK > nframes:
                chunk_size = nframes - chunk_num*CHUNK
            else:
                chunk_size = CHUNK

            # read the next chunk
            chunk = wav_master.readframes ( chunk_size )
            out = struct.unpack_from ( "%dh" % nchannels * chunk_size, chunk )

            # Convert 2 channels to numpy arrays and analyze for drop-outs
            left_master  = np.array (list ( out[0::2] ))
            right_master = np.array (list ( out[1::2] ))

            chunk = wav_donor.readframes ( chunk_size )
            out = struct.unpack_from ( "%dh" % nchannels * chunk_size, chunk )
            left_donor  = np.array (list ( out[0::2] ))
            right_donor = np.array (list ( out[1::2] ))

            # scan the left
            # TODO: zip( left_master, left_donor, right_master, right_donor) ??
            for i in range( len( left_master ) ):

                if left_master[i] == prev_l:
                    donor_l_data.append( left_donor[i] )
                    master_l_data.append( left_master[i] )

                else: # new sample, check if ending a dropout region

                    dropout_len_l = len( master_l_data )
                    if dropout_len_l > thresh: # end of new dropout
                        # this is just a straight copy of the donor into the master
                        # it is tempting to scan the donor for dropouts, but this
                        # adds complexity, and since we know the master has a dropout
                        # in this region, the donor can't be worse, and might even
                        # be better. Copying is simpler, and at worst makes no change.
                        out_l_data.extend( donor_l_data )
                        master_l_data=[ left_master[i] ] 
                        donor_l_data=[ left_donor[i] ]

                    elif dropout_len_l > 0 : # end of duplicate region too short to be a dropout
                        out_l_data.extend( master_l_data )
                        master_l_data=[ left_master[i] ] 
                        donor_l_data=[ left_donor[i] ]

                    else: # no duplicates
                        #out_l_data.append( left_master[ i ] ) 
                        master_l_data=[ left_master[i] ] 
                        donor_l_data=[ left_donor[i] ]

                    # reset 
                    prev_l = left_master[i]
                    dropout_len_l = 0


                # scan the right
                if right_master[i] == prev_r:
                    donor_r_data.append( right_donor[i] )
                    master_r_data.append( right_master[i] )                 

                else: # new sample, check if ending a dropout region

                    dropout_len_r = len( master_r_data )
                    if dropout_len_r > thresh: # end of new dropout
                        out_r_data.extend( donor_r_data )
                        master_r_data=[ right_master[i] ]
                        donor_r_data=[ right_donor[i] ]

                    elif dropout_len_r > 0 : # end of duplicate region too short to be a dropout
                        out_r_data.extend( master_r_data )
                        master_r_data=[ right_master[i] ]
                        donor_r_data=[ right_donor[i] ]

                    else: # no duplicates
                        master_r_data=[ right_master[i] ]
                        donor_r_data=[ right_donor[i] ]
                        #out_r_data.append( right_master[ i ] ) 

                    # reset 
                    prev_r = right_master[i]
                    dropout_len_r = 0

                # flush merged data
                write_len = min( len( out_l_data ), len( out_r_data ) )

                #print( "C:{0:08d} F:{1:09d} M:({2: 06d},{3: 06d})\tD:({4: 06d},{5: 06d})\tL:{6: 06d},{7: 06d}\tout:{8: 06d}:{9: 06d}\twrite:{10: 06d}".format(
                #    chunk_num, frame_num, 
                #    left_master[i], right_master[i],
                #    left_donor[i],  right_donor[i],
                #    len(master_l_data), len(master_r_data), len( out_l_data), len( out_r_data), write_len ), end='\r', flush=True)
                if write_len > 20:
                    print( "C:{0:08d} F:{1:s}\tM:({2: 06d},{3: 06d})\tD:({4: 06d},{5: 06d})\tL:{6: 06d},{7: 06d}\tout:{8: 06d}:{9: 06d}\twrite:{10: 06d}".format(
                        chunk_num, self.sample_to_time( frame_num ), 
                        left_master[i], right_master[i],
                        left_donor[i],  right_donor[i],
                        len(master_l_data), len(master_r_data), len( out_l_data), len( out_r_data), write_len ) )

                if write_len > 0:
                    for (l, r) in zip( out_l_data[:write_len], out_r_data[:write_len] ):
                        wav_out.writeframesraw( struct.pack('<hh', int(l), int(r) ) )

                    out_l_data=out_l_data[write_len:]
                    out_r_data=out_r_data[write_len:]

            frame_num += chunk_size
            print( "C:{0:08d} F:{1:s}".format( chunk_num, self.sample_to_time( frame_num ) ), end='\r', flush=True)

        # close file
        wav_master.close()
        wav_donor.close()
        wav_out.close()
    # END DAT_Fix.do_scan_and_fill_2()

if len(sys.argv) > 1:
    df=DAT_Fix()

    # process argument list as filenames
    file_list=[]
    for fname in sys.argv[1:]:
        datfile={ "name":fname }
        file_list.append(datfile)

    # get information on all files
    for i in range( len(file_list) ):
        df.get_file_info( file_list[i] )
        #df.print_file_info( file_list[i] )
        df.get_leader_length( file_list[i] )
        df.dropout_score( file_list[i] )
        
    #for i in range( len(file_list) ):
    #    print("L: {0:s}\tlead frames: {1:d}".format(
    #        file_list[i][ "name" ], file_list[i][ "leader_length"] ))
        
    #df.median_3( file_list )
                   #df.do_scan_and_fill_2( file_list, thresh=50 )
