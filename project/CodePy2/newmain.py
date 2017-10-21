
#import importlib
import numpy as np
import random
#import matplotlib.pyplot as plt
import subprocess
import os
import funmath
import sys
import multiprocessing as mp
import datetime
from extra.blossom5 import pyMatch
"""
This code will generate qubits, apply error to them, measure the syndrome of the
error, find the least weight matching of the error, and find paths between those
matchings. It will loop over this to determine the failure rate for different
lattice configurations.

This code is multithreaded. It is hardcoded to work on the
@smp-comp-03.smp.uq.edu.au server. Only major modification that would need to be
done to work elsewhere is changing the write directory from the RAM disk
/dev/shm and change the local dir.
- writing to ramdisk halves comp time.

-halfway through converting to use Naomi Nickersons code to interface with
 BlossomV code. Hardcoded to run on dogmatix server. I may need to copy her whole blossom folder? something about PMlib
"""
funmath.clear_all()

def main():
    ####### MAIN PARAMS ###############
    mt = True #turn multithreading on/off
    '''code size'''
    global L
    L =30
    '''number of loops'''
    loops =400
    '''number of threads'''
    threadcount = 20
    '''correlation length'''
    mincorr = 1
    maxcorr = 20
    stepcorr = 1
    '''errrate range'''
    global minerr
    minerr = 0.0
    global maxerr
    maxerr = 0.25
    global steperr
    steperr = 0.001
    ###################################

    global quick
    quick = 1
    global m   #height
    m = L
    global n
    n = L   #width

    #loops = int(input('Choose number of loops: '))
    errtype = 4 
    funmath.tic()

    #set up the multiprocessing
    global output #does a queue need to be global?
    output = mp.Queue(0) #to store data before sorting and printing
    pool = mp.Pool(processes = threadcount) #to create multiple processes
    outlist = []
    ErrRates = np.arange(minerr,maxerr+steperr,steperr)
    
    if mt:
        print('multithreading enabled')
	for ErrorRate in ErrRates:
            processes = pool.apply_async(worker, [ L,loops,errtype,ErrorRate,len(ErrRates), mincorr, maxcorr, stepcorr,mt])
        pool.close()
        pool.join()

            #take the queue, and put into a list
        while output.qsize() != 0: #calling get reduces the size of queue
            got = output.get()
            outlist.append(got)
        outlist.sort()
    else:
        print('Single threaded')
        for ErrorRate in ErrRates:
            outlist.append(worker( L,loops,errtype,ErrorRate,len(ErrRates), mincorr, maxcorr, stepcorr,mt))
    #write the sorted output to file
    filename = ('/data/'+'l'+str(loops)+'L'+str(L)+'E'+str(errtype))
    data = open(filename + ".txt", 'w')
    data.write(' anyons '+',' + ' CorrLen ' +','+ ' q1 failure '+','+' q2 failure '+', Average manhatten distance'+'\n')

    for k in outlist:
        data.write(str(k[0])+',    ' + str(k[1]) +',    '+ str(k[2])+',    '+str(k[3])+ ',    '+str(k[4])+'\n')

def worker(L,loops,errtype,ErrorRate,errlen, mincorr, maxcorr, stepcorr,mt):
    pid =str(os.getpid()) #unique ID for each parallel process
    if errtype==5 or errtype == 4:
        er = ErrorRate
        ErrorRate = int(ErrorRate*L*L) #convert to number of errors

    for CorrLen in range(mincorr,maxcorr+stepcorr,stepcorr):#length of correlation
        if CorrLen*ErrorRate >= L*L*0.3: #skip any with too much error
            continue
        total1 = 0
        total2 = 0
        zMTotal = 0 #store manhatten distance
        matchtotal = 0 #store match distance

        for loopcounter in range(loops):
            #create the qubit array
            blankarray = funmath.createarray(m,n)
            

            #Apply X errors (E) to the qubits
            ErrorArray = funmath.ApplyXErrors(ErrorRate,np.array(blankarray),errtype,L, CorrLen)

            #Generate syndrome
            PSyndrome = funmath.Measure_Syndrome(ErrorArray,m,n)

            #search through syndrome and add defects to a list
                #Could make this part of the syndrome measurement
            vertices = funmath.FindDefects(PSyndrome)
          
            #check if any errors need fixing
            if len(vertices)==0:
                continue#if not, then move on.
                    #Find Manhatten distance
            zM = funmath.Manhatten_Distance(vertices,m,n)
            #Creating the TSPLIB file
                #Parameters for TSPLIB file
            graph=[]
       

                #write manhatten distances
            for row in range(0,len(zM[:,0])-1):
                for col in range(row+1,len(zM[:,0])):
                    graph.append([row,col,int(zM[row,col])])


            ##call the blossom5 code on the generated syndrome

            matching = pyMatch.getMatching(len(vertices),graph)
            #process nickerson output
            pairs = []
            for i in range(0,len(matching),2):
                pairs.append([matching[i],matching[i+1]])
            #create an array counting up
                #this is better done with a dict
            refarray = np.zeros((m,n))
            refdict={}
            counter = 1 #counter could be repalced by i+j
            for i in range(len(refarray[:,0])):
                for j in range(len(refarray[0,:])):
                    refarray[i,j] = counter
                    refdict[counter] =[i,j]
                    counter +=1
            #calculating paths
            ## #my algorithm - VERY FAST

            custompath=[]

            for i in pairs:
                p1 = list(vertices[i[0]])
                p2 = list(vertices[i[1]])
                custompath.append(funmath.CustomShortestPath(p1,p2,m,n))

            paths = custompath

            #now we convert the paths into the actual bits that get flipped
            CorrectionArray = funmath.GetFlippedPoints(paths,blankarray)

            #now we apply the corrections
            CorrectedArray = np.multiply(ErrorArray,CorrectionArray)
            CorrectedArray = np.array(CorrectedArray)

            #now we test for a failure
            qubit1 = 1
            qubit2 = 1

            for i in CorrectedArray[0,0,:]:
                qubit1 = qubit1*i

            for i in CorrectedArray[:,1,0]:
                qubit2 = qubit2*i

            if qubit1 == -1:
                total1+=1
            if qubit2 ==-1:
                total2+=1
            zMTotal += np.mean(zM)
            #matchtotal +=



        zMavg = 1.0*zMTotal/loopcounter

        if mt:

            queuelen = int(output.qsize())
	    
            print(str([ErrorRate, CorrLen, 1.0*total1/loops, 1.0*total2/loops,zMavg])+'   % done = '+str(100.0*(queuelen)/(maxcorr-mincorr+1)/stepcorr/errlen)+'    '+str(datetime.datetime.now().isoformat())) #step err has int errors. this counter isnt accurate.

            output.put([ErrorRate, CorrLen, 1.0*total1/loops, 1.0*total2/loops,zMavg])
            sys.stdout.flush() #this is needed otherwise the output will be
                   #stored in a buffer and not written to nohup.out
        else:
            return([ErrorRate, CorrLen, 1.0*total1/loops, 1.0*total2/loops,zMavg])

if __name__ == '__main__':
    #os.system('mkdir /dev/shm/s4318965/')
    main()
    #os.system('rm -rf /dev/shm/s4318965/')
    print('Code Complete')
funmath.toc()