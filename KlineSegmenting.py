# -*- coding: utf-8 -*-
"""
Created on Thu Jul 15 23:21:07 2021

@author: L
"""


from interval import Interval
import mpl_finance
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
#import datetime
#from matplotlib.pylab import date2num

def intervalCompute(intvA, intvB):
    # 计算A、B区间是否重叠，如有，则返回重叠部分，否则返回方向关系（b > a则为up反之down），和None
    if intvA.overlaps(intvB):        
        intvRet = Interval(max((intvA.lower_bound, intvB.lower_bound)), min((intvA.upper_bound, intvB.upper_bound)))
        return "overlap", intvRet
    elif intvA.upper_bound < intvB.lower_bound:
        return "up", None
    else:
        return "down", None
    
    
def isIncluding(intvA, intvB):
    # 计算AB是否为包含关系，只要一方包含另一方，则返回True， 否则False
    isOverlap, intvOvlp = intervalCompute(intvA, intvB)
    if isOverlap == "overlap" and intvOvlp == intvA:
        # 重复段为前者，即后包前
        return True, 0
    if isOverlap == "overlap" and intvOvlp == intvB:
        # 重复段为后者，即前包后
        return True, 1
    else:
        # 无包含关系
        return False, None
    
def includingProcess(intvA, intvB, direction="up"):
    # 计算相互有包含关系的A、B合并后的新区间，拟缠论规则
    if direction == "up":
        return Interval(max((intvA.lower_bound, intvB.lower_bound)), max((intvA.upper_bound, intvB.upper_bound)))
    elif direction == "down":
        return Interval(min((intvA.lower_bound, intvB.lower_bound)), min((intvA.upper_bound, intvB.upper_bound)))
            
def _reviseInclude(dfKlinesCopy, intvRet, close, iloc):
    # 辅助函数，用于最后按包含关系修改dfKlinesCopy
    dfKlinesCopy.iat[iloc, 2] = intvRet.upper_bound
    dfKlinesCopy.iat[iloc, 3] = intvRet.lower_bound
    dfKlinesCopy.iat[iloc, 4] = close
#    dfKlinesCopy["HIGH"][iloc] = intvRet.upper_bound
    return dfKlinesCopy


def _exInclude(dfKlines):
    # 私有函数，处理包含关系,lastValid和lstValid用于在后面的遍历中标识有意义的K线的记录
    # 同时为避免破坏数据源，先制作了一个备份变量dfKlinesCopy
    lastValid = 1; lstValid = [dfKlines.index[0]]
#    lastValid = 0; lstValid = [dfKlines.index[0]] 修改前
    dfKlinesCopy = dfKlines.copy()
    
    for i, idx in enumerate(dfKlines.index):
        # 把当日股价运行区间变换成一个区间对象，以便用上面的“intervalCompute”
        intvKi = Interval(dfKlines.iat[i, 3], dfKlines.iat[i, 2])
        intvLast = Interval(dfKlinesCopy.iat[lastValid, 3], dfKlinesCopy.iat[lastValid, 2])      
#        intvKi = Interval(dfKlines["LOW"][i], dfKlines["HIGH"][i])
#        intvLast = Interval(dfKlinesCopy["LOW"][lastValid], dfKlinesCopy["HIGH"][lastValid])
        
        if i > 1 :
            biIn, inType = isIncluding(intvLast, intvKi)
            if not biIn:
                # 如果没有包含关系，不改动数据
                lastValid = i
                lstValid.append(idx)
                direction = "up" if dfKlines.iat[lastValid, 2] >= dfKlines.iat[lastValid-1, 2] else "down"
#                direction = "up" if dfKlines["HIGH"][lastValid] >= dfKlines["HIGH"][lastValid-1] else "down"
                intvRet = includingProcess(intvLast, intvKi, direction)
                if inType == 1:
                    dfKlinesCopy = _reviseInclude(dfKlinesCopy, intvRet, dfKlines.iat[i, 4], lastValid)
#                    dfKlinesCopy = _reviseInclude(dfKlinesCopy, intvRet, dfKlines["CLOSE"][i], lastValid)
                elif inType == 0:
                    dfKlinesCopy = _reviseInclude(dfKlinesCopy, intvRet, dfKlines.iat[i, 4], i)
#                    dfKlinesCopy = _reviseInclude(dfKlinesCopy, intvRet, dfKlines["CLOSE"][i], i)
                    lastValid = i
                    lstValid.pop()
                    lstValid.append(idx)

    # 最后，我们只输出在lstValid中的数据
    dfRet = dfKlinesCopy.loc[lstValid]
    return dfRet


def getInflection(dfK):    
    srsMax, srsMin = dfK["HIGH"].rolling(5).max().shift(-2), dfK["LOW"].rolling(5).min().shift(-2)
    lstUp = list(dfK.loc[dfK["HIGH"] == srsMax].index)
    lstDown = list(dfK.loc[dfK["LOW"] == srsMin].index)
    return lstUp, lstDown


def getRet(dfK, lstUp, lstDown):
    dfRet = pd.DataFrame(index=sorted(lstUp + lstDown), columns=["ALL", "pointType"]) 
    dfRet.loc[lstUp, "ALL"] = dfK.loc[lstUp, "HIGH"]
    dfRet.loc[lstUp, "pointType"] = 1
    dfRet.loc[lstDown, "ALL"] = dfK.loc[lstDown, "LOW"]
    dfRet.loc[lstDown, "pointType"] = -1
    return dfRet


def dropSameDirection(dfRet):
    dictSeg = []; flag = 0
    for i,d in enumerate(dfRet.index):
        if i >= 1:
#            if dfRet.pointType[i] == dfRet.pointType[i-1]:
            if dfRet.iat[i, 1] == dfRet.iat[i-1, 1]:
                if flag == 0:
                    tempList = [dfRet.index[i-1], d]
                    flag = 1
                else:
                    tempList.append(d)
            elif flag == 1:
                    dictSeg.append(tempList)
                    flag = 0
                    continue
            if d == dfRet.index[-1] and flag == 1:
                dictSeg.append(tempList)

    if len(dictSeg):
        lst2drop = []
        for lst in dictSeg: 
            if dfRet.loc[lst[0] , 'pointType'] == 1: 
                index_max_or_min = lst[pd.to_numeric(dfRet.loc[lst, 'ALL']).argmax()]
#                lst.remove(pd.to_numeric(dfRet.loc[lst, "ALL"]).argmax())
            else:
                index_max_or_min = lst[pd.to_numeric(dfRet.loc[lst, 'ALL']).argmin()]
#                lst.remove(pd.to_numeric(dfRet.loc[lst, "ALL"]).argmin())
            lst.remove(index_max_or_min) 
            lst2drop += lst
    
        dfRet.drop( lst2drop, inplace=True)    


def dropNearPunc(dfRet, dfK):
    dfRet["locInK"] = [dfK.index.get_loc(d) for d in dfRet.index]    
    lst2BeDropped = []; flag = 0

    for i, d in enumerate(dfRet.index):
        if flag : 
            flag = 0
            continue
        if i > 1 and d != dfRet.index[-1] and (dfRet.iat[i+1, 2] - dfRet.iat[i, 2] <= 3):#locInK是第2列
#        if i > 1 and d != dfRet.index[-1] and (dfRet.locInK[i+1] - dfRet.locInK[i] <= 3):

            if dfRet.iat[i, 1] == 1:   
#            if dfRet.pointType[i] == 1:
                if dfRet.iat[i+1, 2] >= dfRet.iat[i-1, 2]:
#                if dfRet.ALL[i+1] >= dfRet.ALL[i-1]:
                    lst2BeDropped.append(d)
                    lst2BeDropped.append(dfRet.index[i+1])                    
                    flag = 1
            else:
                if dfRet.iat[i+1, 0] <= dfRet.iat[i-1, 0]:
#                if dfRet.ALL[i+1] <= dfRet.ALL[i-1]:
                    lst2BeDropped.append(d)
                    lst2BeDropped.append(dfRet.index[i+1])                    
                    flag = 1
    lstValid = sorted(set(dfRet.index).difference(lst2BeDropped))
    return dfRet.loc[lstValid]


def readKlineFile(fn):
    df = pd.read_csv(fn).iloc[:, [0,2,3,4,5]]#直接剔除code这列，后面无需使用
    df.columns = ['date', 'OPEN', 'HIGH', 'LOW', 'CLOSE']
    return  df 


def generatePunc(fn, start_date, end_date):  
    dfKlines = readKlineFile(fn)
    dfKlines = dfKlines[ (dfKlines.iloc[:,0]>= start_date) & 
                         (dfKlines.iloc[:,0]<= end_date) ]
    dfKlines = dfKlines.reset_index(drop=True)
    
    dfK = _exInclude(dfKlines) 
    # 通过滚动算法，找到符合顶分型、底分型的K线，存在lstUp和lstDown里面
    lstUp, lstDown = getInflection(dfK)
    # 将这些代表“拐点”的分型存入dfRet中，准备进一步过滤
    dfRet = getRet(dfK, lstUp, lstDown)

    # 去除同向相连的情况
    dropSameDirection(dfRet)
    
    # 去除二点过近且波动意义不大的情况
    dfRet = dropNearPunc(dfRet, dfK)
    
    # 将终结点与最后一个拐点连接
    if not dfKlines.index[-1] in dfRet.index:
        dr = "up" if dfRet.iat[-1, 1] == -1 else "down"
        dfRet.loc[dfKlines.index[-1], "ALL"] = dfKlines.loc[dfKlines.index[-1], "HIGH"] \
            if dr == "up" else dfKlines.loc[dfKlines.index[-1], "LOW"]
    return dfKlines, dfRet


def plotK(dfKlines, dfRet, code):
    lst = np.array(dfKlines)
    lst[:,0] = range(len(lst))

    fig, ax = plt.subplots(figsize=(16, 10))
    plt.plot( dfRet['ALL'], color='k', linewidth=1 )
    mpl_finance.candlestick_ohlc(ax, lst, width=0.6, alpha=0.8, colordown='#53c156', colorup='#ff1717')
    ax.grid(True)
    plt.title('%s %s %s'%(code, start_date, end_date))
    plt.savefig(r'C:\pv\KlineSegmenting\%s %s %s.png'%(code, start_date, end_date), dpi=200 )
    plt.close()


def main(fn, start_date, end_date ):
    code = fn[-10:-4] 
    dfKlines, dfRet = generatePunc(fn, start_date, end_date)
    plotK(dfKlines, dfRet, code)


def getfn(path):
    out = []
    for root, dirs, files in os.walk(path):
        for file in files:
            out.append(os.path.join(root, file))
    return out


if __name__ == '__main__':    
    start_date = '2021-02-01'
    end_date = '2021-08-01'        
    fn_lis = getfn(r'C:\pv\baostock data\index20220121')
    for fn in fn_lis:
        main(fn, start_date, end_date)



