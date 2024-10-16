import networkx as nx
import matplotlib.pyplot as plt

import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import spsolve
import pandas as pd
import mrtkz3 as mrtkz
import numpy as np
from collections import deque
import itertools
#import copy




''' Функции, добавленные к библиотеке mrtkz3 Артуром Клементом'''
# тестовая модель, используется для тестирования функций
def base_model():
    mdl=mrtkz.Model()

    #Создание узлов

    q1 = mrtkz.Q(mdl,'PS1', x=1,y=3)
    q2 = mrtkz.Q(mdl,'PS2', x=3,y=3)
    q3 = mrtkz.Q(mdl,'PS3', x=2,y=2)
    q4 = mrtkz.Q(mdl,'PS4', x=1,y=4)
    q5 = mrtkz.Q(mdl,'PS5', x=3,y=4)

    #Создание ветвей энергосистем
    Sys1 = mrtkz.P(mdl,'Sys1',0,q5,(2j,2j,3j),E=(65000,0,0))
    Sys2 = mrtkz.P(mdl,'Sys2',0,q3,(2j,2j,3j),E=(65000,0,0))

    #Создание ветвей Воздушных линий
    Line1 = mrtkz.P(mdl,'PS1-PS2',q1,q2,(10j,10j,30j))
    Line2 = mrtkz.P(mdl,'PS1-PS3',q1,q3,(10j,10j,30j))
    Line3 = mrtkz.P(mdl,'PS2-PS3',q2,q3,(10j,10j,30j))
    Line4 = mrtkz.P(mdl,'PS1-PS4',q1,q4,(10j,10j,30j))
    Line5 = mrtkz.P(mdl,'PS2-PS5',q2,q5,(10j,10j,30j))
    Line6 = mrtkz.P(mdl,'PS4-PS5',q4,q5,(10j,10j,30j))
    #Создание взаимоиндукций нулевой последовательности между Воздушными линиями
    M12 = mrtkz.M(mdl,'L4-L5',Line4,Line5,15j,15j)

    #Создание ветвей подстанций с трансформаторами с заземленными нейтралями
    T1 = mrtkz.P(mdl,'PS1',0,q1,(500,200j,30j))
    T2 = mrtkz.P(mdl,'PS2',0,q2,(500,200j,30j))
    T4 = mrtkz.P(mdl,'PS4',0,q4,(500,200j,30j))

    #Добавление защит
    '''
    pr1 = mrtkz.protection(p=Line2, q=Line2.q1, stage=1, I0=3000, t=0, type='ТЗНП', P_rnm=0, rnm_base_angle=0, stage_on = True, I0_range=[300,3000], t_range=[0,20], desc='')
    pr2 = mrtkz.protection(p=Line2, q=Line2.q1, stage=2, I0=1000, t=5, type='ТЗНП', P_rnm=0, rnm_base_angle=0, stage_on = True, I0_range=[300,3000], t_range=[0,20], desc='')
    pr3 = mrtkz.protection(p=Line5, q=Line5.q2, stage=1, I0=1000, t=0, type='ТЗНП', P_rnm=0, rnm_base_angle=0, stage_on = True, I0_range=[300,3000], t_range=[0,20], desc='')
    #mdl.bp[3].q1_def[1].I0 - вызов параметров релейной защиты
    '''
    #Добавление по 4 ступени на узел
    for p in mdl.bp:
        for i in range(1,5):
            I = 4000 - i*1000
            t = i - 1
            if p.q1!=0: mrtkz.protection(p=p, q=p.q1, stage=i, I0=I, t=t, type='ТЗНП', P_rnm=0, rnm_base_angle=0, stage_on = True, I0_range=[300,3000], t_range=[0,20], desc='')
            if p.q2!=0: mrtkz.protection(p=p, q=p.q2, stage=i, I0=I, t=t, type='ТЗНП', P_rnm=0, rnm_base_angle=0, stage_on = True, I0_range=[300,3000], t_range=[0,20], desc='')
    mrtkz.protection(p=Line5, q=Line5.q2, stage=9, I0=0, t=1.75, type='ТЗНП', P_rnm=0, rnm_base_angle=0, stage_on = True, I0_range=[300,3000], t_range=[0,20], desc='')
    #Формирование разреженной СЛАУ и расчет электрических параметров
    #mdl.Calc()
    #  Проверка на вырожденность
    mdl.Test4Singularity()
    return mdl


'''
КОПИЯ Функция создает узел промежуточного КЗ, создает линии для жтого участка, удаляет общую линию. Возвращает список из Двух линий и узла.
Функция два раза переписывает модель, один раз исполняя функцию duplicate_mdl(), второй раз во время p_del(). Очевидная оптимизация - переписать эту функцию, сделав ее похожей на p_del(), но с дорисовыванием двух ветвей и узла.

Также есть функция каскада. Если kaskade=True, то функция возвращает 3 модели обычную и двсе с отключенными участками линии вокруг кз
'''


def kz_q(mdl, line, percentage_of_line=0.5, show_G=True, show_par=False, kaskade=False):

    if line.q1 == 0:
        q_x = line.q2.x + 0.25*percentage_of_line
        q_y = line.q2.y - 0.5*percentage_of_line
        
    elif line.q2 == 0:
        q_x = line.q1.x + 0.5*percentage_of_line
        q_y = line.q1.y + 1*percentage_of_line        
    else:
        q_x = line.q1.x + (line.q2.x - line.q1.x)*percentage_of_line
        q_y = line.q1.y + (line.q2.y - line.q1.y)*percentage_of_line

    #print(q_x, q_y)
    sub_mdl = duplicate_mdl(mdl, show_G = False)
    
    #sub_mdl=mrtkz.Model()
    #sub_mdl = mdl
    #sub_mdl.Calc()# delete
    #print(sub_mdl.bq)
    KZ_q = mrtkz.Q(sub_mdl,'KZ', x=q_x, y=q_y) # создаем узел КЗ
    if show_par: print("X: ",KZ_q.x,"Y: ", KZ_q.y)
    #sub_mdl.Calc()# delete
    #print(sub_mdl.bq)
    try:
        q1_name = line.q1.name
        q1_sub = q_search(sub_mdl,q_name=q1_name) # ищим узел с таким же названием в подмодели как в модели mdl линии line
        Zq1=tuple(percentage_of_line * elem for elem in line.Z) # рассчитываем сопротивление участка q1-кз
        q1_kz_line = mrtkz.P(sub_mdl,'q1-kz',q1_sub,KZ_q,Zq1) # вводим участок q1-кз # !!!!!!!!!!!!воткнуть поиск узла   
        # добавляем защиты линии
        if line.q1 != 0:
            for prot1 in line.q1_def:
                mrtkz.protection(p=q1_kz_line, q=q1_kz_line.q1, stat_id=prot1.stat_id, type=prot1.type, stage=prot1.stage, I0=prot1.I0, t=prot1.t, P_rnm=prot1.P_rnm, rnm_base_angle=prot1.rnm_on, stage_on = prot1.stage_on, I0_range=prot1.I0_range, t_range=prot1.t_range, desc=prot1.desc, k_ch=prot1.k_ch, k_ots=prot1.k_ots, k_voz=prot1.k_voz)
        
    except: 1
        
    try:
        q2_name = line.q2.name
        q2_sub = q_search(sub_mdl,q_name=q2_name) # ищим узел с таким же названием в подмодели как в модели mdl линии line
        Zq2=tuple((1-percentage_of_line) * elem for elem in line.Z) # рассчитываем сопротивление участка q2-кз
        kz_q2_line = mrtkz.P(sub_mdl,'kz-q2',KZ_q, q2_sub, Zq2) # вводим участок q2-кз
        # добавляем защиты линии
        if line.q2 != 0:
            for prot1 in line.q2_def:
                mrtkz.protection(p=kz_q2_line, q=kz_q2_line.q2, stat_id=prot1.stat_id, type=prot1.type, stage=prot1.stage, I0=prot1.I0, t=prot1.t, P_rnm=prot1.P_rnm, rnm_base_angle=prot1.rnm_on, stage_on = prot1.stage_on, I0_range=prot1.I0_range, t_range=prot1.t_range, desc=prot1.desc, k_ch=prot1.k_ch, k_ots=prot1.k_ots, k_voz=prot1.k_voz)
    except: 1

    # добавляем взаимоиндукции с линией кз, делим проводимости в отношении % кз
    if line.mlist != []:
        for m in line.mlist:
            M12 = m.M12
            M21 = m.M21
            if m.p1.name == line.name:
                name = 'q1_kz-'+ m.p2.name
                p = p_search(sub_mdl, p_name=m.p2.name)
                mrtkz.M(sub_mdl,name,q1_kz_line,p,M12*percentage_of_line,M21*percentage_of_line)
                mrtkz.M(sub_mdl,name,kz_q2_line,p,M12*(1-percentage_of_line),M21*(1-percentage_of_line))
            else:
                name = 'kz_q2-'+ m.p1.name
                p = p_search(sub_mdl, p_name=m.p1.name)
                mrtkz.M(sub_mdl,name,q1_kz_line,p,M12*percentage_of_line,M21*percentage_of_line)
                mrtkz.M(sub_mdl,name,kz_q2_line,p,M12*(1-percentage_of_line),M21*(1-percentage_of_line))
    
    sub_mdl_2 = p_del(sub_mdl, del_p_name=line.name, show_G=show_G) # Удаляем общую ветвь
    # если каскад, то создаем две дополнительные модели с удаленными линиями вокруг узла кз
    if kaskade:
        if show_G: print('Каскад')
        try: sub_mdl_q1 = p_del(sub_mdl_2, del_p_name=q1_kz_line.name, show_G=False) # Удаляем общую ветвь
        except: sub_mdl_q1= ''
        try: sub_mdl_q2 = p_del(sub_mdl_2, del_p_name=kz_q2_line.name, show_G=False)
        except: sub_mdl_q2 = ''
        return sub_mdl_2, sub_mdl_q1, sub_mdl_q2
    else: 
        return sub_mdl_2


'''
Функция создает подрежим в котором удален узел "del_q_name" по имени узла q.name. Также удаляются ветви, связанные с этим узлом
'''
def q_del(mdl, del_q_name, show_G=True):
    submdl=mrtkz.Model() # создаем подрежим
    submdl.Clear()
    submdl=mrtkz.Model()
    # проходимся по узлам основной модели и добавляем в новый подрежим все, кроме удаляемого 
    for i in mdl.bq:
        if i.name != del_q_name:
            mrtkz.Q(submdl,name=i.name, x=i.x,y=i.y)
        else:
            q_del_obj = i
            print('Удален узел', i.name)

    # ищем линии, которые не содержат удаляемый узел       
    for p in mdl.bp:
        if p not in q_del_obj.plist:
            # ищем узлы линии mdl и записываем их в переменные q1, q2 чтобы внести ветви в подрежим
            if p.q1 == 0:
                q1 = 0
            elif p.q2 == 0:
                q2 = 0
            
            for q in submdl.bq:
                try:
                    if q.name == p.q2.name:
                        q2 = q
                    elif q.name == p.q1.name:
                        q1 = q
                    else:
                        q
                except:
                    q
            # добавляем все вретви, не связанные с удаляемым узлом в подрежим
            mrtkz.P(submdl,name=p.name,q1=q1,q2=q2,Z=p.Z,E=p.E,T=p.T,B=p.B,desc=p.desc)
            
            # добавляем в подрежим РЗ
            for prot1 in p.q1_def:
                mrtkz.protection(p=submdl.bp[-1], q=submdl.bp[-1].q1, stat_id=prot1.stat_id, type=prot1.type, stage=prot1.stage, I0=prot1.I0, t=prot1.t, P_rnm=prot1.P_rnm, rnm_base_angle=prot1.rnm_on, stage_on = prot1.stage_on, I0_range=prot1.I0_range, t_range=prot1.t_range, desc=prot1.desc, k_ch=prot1.k_ch, k_ots=prot1.k_ots, k_voz=prot1.k_voz)
            
            for prot1 in p.q2_def:
                mrtkz.protection(p=submdl.bp[-1], q=submdl.bp[-1].q2, stat_id=prot1.stat_id, type=prot1.type, stage=prot1.stage, I0=prot1.I0, t=prot1.t, P_rnm=prot1.P_rnm, rnm_base_angle=prot1.rnm_on, stage_on = prot1.stage_on, I0_range=prot1.I0_range, t_range=prot1.t_range, desc=prot1.desc, k_ch=prot1.k_ch, k_ots=prot1.k_ots, k_voz=prot1.k_voz)

    # добавляем в подрежим взаимоиндукции
    try:
        for m in mdl.bm:
            p1 = p_search(mdl=submdl,p_name=m.p1.name)
            p2 = p_search(mdl=submdl,p_name=m.p2.name)
            mrtkz.M(model=submdl,name=m.name,p1=p1,p2=p2,M12=m.M12,M21=m.M21,desc=m.desc)
    except: 1
    # добавляем в подрежим несимметрии
    try:
        for n in mdl.bn:
            mrtkz.N(model=submdl,name=n.name,qp=q_search(submdl,n.qp.name),SC=n.SC,r=n.r,desc=n.desc)     
    except: 1
        
    submdl.Calc()
    if show_G:
        print_G(submdl)
    return submdl

'''
V3 Функция удаляет ветвь и ее узлы, если они тупиковые
'''
def p_del(mdl, del_p_name=[],q1_name='', q2_name='', show_G=True, show_par=False, node = False):
    
    if (del_p_name==[]) and (q1_name=='' or q2_name==''):
        print('Ведите название линии в del_p_name или названия узлов в q1_name и q2_name')
        return
    if (del_p_name!=[]) and (q1_name!='' or q2_name!=''):
        print('Ведите либо название линии в del_p_name, либо названия узлов в q1_name и q2_name. Не одновременно.')
        return
    submdl=mrtkz.Model() # создаем подрежим
    submdl.Clear()
    submdl=mrtkz.Model()
    q_list = []
    if isinstance(del_p_name, tuple):
        del_p_name = list(del_p_name)
    elif isinstance(del_p_name, str):
        del_p_name = [del_p_name]
    elif not isinstance(del_p_name, list):
        raise ValueError("del_p_name должен быть строкой, кортежем или списком")

    #if (del_p_name, tuple): del_p_name = list(del_p_name)
    #elif not isinstance(del_p_name, list): 
    #    temp_var = []
    #    temp_var.append(del_p_name)
    #    del_p_name = temp_var
    # блок, определяющий связный ли получается граф и если не связный, то оставляет только линии которые пренадлежат к узлу node
    if node == False:
        lines = '' 
        connected_G = True
    else:
        temp_G = mdl.G.copy()
        for p_name in del_p_name:
            p = p_search(mdl,p_name=p_name)
            try:        
                q1_G_name = p.q1.name
            except:
                q1_G_name = p.name + '_0'
            try:
                q2_G_name = p.q2.name
            except:
                q2_G_name = p.name + '_0'
            
            
            temp_G.remove_edge(q1_G_name, q2_G_name)
        
        # Проверим, является ли граф связным
        if not nx.is_connected(temp_G):
            connected_G = False
            #print("Граф несвязный")
            # Поиск рёбер в глубину, начиная с узла
            edges = list(nx.dfs_edges(temp_G, source=node))  # Получаем только узлы рёбер
            
            # Извлекаем названия линий
            lines = []
            for u, v in edges:
                edge_data = temp_G.get_edge_data(u, v)
                if 'name' in edge_data:
                    lines.append(edge_data['name'])
            #print(f"Названия линий, связанных с узлом {node}: {lines}")                  
        else:
            lines = '' 
            connected_G = True   
            #print("Граф связный")

    for p in mdl.bp:
        # решаем проблему с тем что узел может быть узлом, а может нулем
        try:        
            q1_p_name = p.q1.name
        except:
            q1 = 0
            q1_p_name = '0'
        try:
            q2_p_name = p.q2.name
        except:
            q2 = 0
            q2_p_name = '0'
        # для остальных ветвей
        if (p.name not in del_p_name) and not ((q1_p_name == q1_name and q2_p_name == q2_name) or (q1_p_name == q2_name and q2_p_name == q1_name)) and ((p.name in lines) or connected_G):
            # создаем узлы, проверяя что они не нулевые и их еще нет в модели (используем для этого список уже добавленных листов)
            if (q1_p_name!='0') and (q1_p_name not in q_list):   
                mrtkz.Q(submdl,name=q1_p_name, x=p.q1.x,y=p.q1.y)
                q_list.append(q1_p_name)

            if (q2_p_name!='0') and (q2_p_name not in q_list):   
                mrtkz.Q(submdl,name=q2_p_name, x=p.q2.x,y=p.q2.y)
                q_list.append(q2_p_name)  
            for q in submdl.bq:
                if q.name == q1_p_name:
                    q1 = q
                if q.name == q2_p_name:
                    q2 = q    
            # добавляем в подрежим ветвь    
            mrtkz.P(submdl,name=p.name,q1=q1,q2=q2,Z=p.Z,E=p.E,T=p.T,B=p.B,desc=p.desc)

            # добавляем в подрежим РЗ
            for prot1 in p.q1_def:
                mrtkz.protection(p=submdl.bp[-1], q=submdl.bp[-1].q1, stat_id=prot1.stat_id, type=prot1.type, stage=prot1.stage, I0=prot1.I0, t=prot1.t, P_rnm=prot1.P_rnm, rnm_base_angle=prot1.rnm_on, stage_on = prot1.stage_on, I0_range=prot1.I0_range, t_range=prot1.t_range, desc=prot1.desc, k_ch=prot1.k_ch, k_ots=prot1.k_ots, k_voz=prot1.k_voz)
            
            for prot1 in p.q2_def:
                mrtkz.protection(p=submdl.bp[-1], q=submdl.bp[-1].q2, stat_id=prot1.stat_id, type=prot1.type, stage=prot1.stage, I0=prot1.I0, t=prot1.t, P_rnm=prot1.P_rnm, rnm_base_angle=prot1.rnm_on, stage_on = prot1.stage_on, I0_range=prot1.I0_range, t_range=prot1.t_range, desc=prot1.desc, k_ch=prot1.k_ch, k_ots=prot1.k_ots, k_voz=prot1.k_voz)

        # если это удаляемая ветвь
        else:
            if show_par: print('Удаляем ветвь', p.name)           
    # добавляем в подрежим взаимоиндукции

    for m in mdl.bm:
        try:
            p1 = p_search(mdl=submdl,p_name=m.p1.name, info=False)
            p2 = p_search(mdl=submdl,p_name=m.p2.name, info=False)
            mrtkz.M(submdl,m.name,p1,p2,m.M12,m.M21,m.desc)
        except: continue
            
    # добавляем в подрежим несимметрии
    for n in mdl.bn:
        try:
            mrtkz.N(model=submdl,name=n.name,qp=q_search(submdl,n.qp.name, info=False),SC=n.SC,r=n.r,desc=n.desc)  
        except: continue

    if show_G:
        print_G(submdl)
    return submdl

# V2 функции удалить, если все работает
def p_del_old(mdl, del_p_name=[],q1_name='', q2_name='', show_G=True, show_par=False):
    
    if (del_p_name==[]) and (q1_name=='' or q2_name==''):
        print('Ведите название линии в del_p_name или названия узлов в q1_name и q2_name')
        return
    if (del_p_name!=[]) and (q1_name!='' or q2_name!=''):
        print('Ведите либо название линии в del_p_name, либо названия узлов в q1_name и q2_name. Не одновременно.')
        return
    submdl=mrtkz.Model() # создаем подрежим
    submdl.Clear()
    submdl=mrtkz.Model()
    q_list = []
    if isinstance(del_p_name, tuple):
        del_p_name = list(del_p_name)
    elif isinstance(del_p_name, str):
        del_p_name = [del_p_name]
    elif not isinstance(del_p_name, list):
        raise ValueError("del_p_name должен быть строкой, кортежем или списком")

    #if (del_p_name, tuple): del_p_name = list(del_p_name)
    #elif not isinstance(del_p_name, list): 
    #    temp_var = []
    #    temp_var.append(del_p_name)
    #    del_p_name = temp_var
    for p in mdl.bp:
        # решаем проблему с тем что узел может быть узлом, а может нулем
        try:        
            q1_p_name = p.q1.name
        except:
            q1 = 0
            q1_p_name = '0'
        try:
            q2_p_name = p.q2.name
        except:
            q2 = 0
            q2_p_name = '0'
        # для остальных ветвей
        if (p.name not in del_p_name) and not ((q1_p_name == q1_name and q2_p_name == q2_name) or (q1_p_name == q2_name and q2_p_name == q1_name)):
            # создаем узлы, проверяя что они не нулевые и их еще нет в модели (используем для этого список уже добавленных листов)
            if (q1_p_name!='0') and (q1_p_name not in q_list):   
                mrtkz.Q(submdl,name=q1_p_name, x=p.q1.x,y=p.q1.y)
                q_list.append(q1_p_name)

            if (q2_p_name!='0') and (q2_p_name not in q_list):   
                mrtkz.Q(submdl,name=q2_p_name, x=p.q2.x,y=p.q2.y)
                q_list.append(q2_p_name)  
            for q in submdl.bq:
                if q.name == q1_p_name:
                    q1 = q
                if q.name == q2_p_name:
                    q2 = q    
            # добавляем в подрежим ветвь    
            mrtkz.P(submdl,name=p.name,q1=q1,q2=q2,Z=p.Z,E=p.E,T=p.T,B=p.B,desc=p.desc)

            # добавляем в подрежим РЗ
            for prot1 in p.q1_def:
                mrtkz.protection(p=submdl.bp[-1], q=submdl.bp[-1].q1, stat_id=prot1.stat_id, type=prot1.type, stage=prot1.stage, I0=prot1.I0, t=prot1.t, P_rnm=prot1.P_rnm, rnm_base_angle=prot1.rnm_on, stage_on = prot1.stage_on, I0_range=prot1.I0_range, t_range=prot1.t_range, desc=prot1.desc, k_ch=prot1.k_ch, k_ots=prot1.k_ots, k_voz=prot1.k_voz)
            
            for prot1 in p.q2_def:
                mrtkz.protection(p=submdl.bp[-1], q=submdl.bp[-1].q2, stat_id=prot1.stat_id, type=prot1.type, stage=prot1.stage, I0=prot1.I0, t=prot1.t, P_rnm=prot1.P_rnm, rnm_base_angle=prot1.rnm_on, stage_on = prot1.stage_on, I0_range=prot1.I0_range, t_range=prot1.t_range, desc=prot1.desc, k_ch=prot1.k_ch, k_ots=prot1.k_ots, k_voz=prot1.k_voz)

        # если это удаляемая ветвь
        else:
            if show_par: print('Удаляем ветвь', p.name)           
    # добавляем в подрежим взаимоиндукции
    try:
        for m in mdl.bm:
            p1 = p_search(mdl=submdl,p_name=m.p1.name, info=False)
            p2 = p_search(mdl=submdl,p_name=m.p2.name, info=False)
            mrtkz.M(model=submdl,name=m.name,p1=p1,p2=p2,M12=m.M12,M21=m.M21,desc=m.desc)
    except: 1
    # добавляем в подрежим несимметрии
    try:
        for n in mdl.bn:
            mrtkz.N(model=submdl,name=n.name,qp=q_search(submdl,n.qp.name, info=False),SC=n.SC,r=n.r,desc=n.desc)  
    except: 1
    if show_G:
        print_G(submdl)
    return submdl

'''
Функция удаляет ветвь и ее узлы, если они тупиковые
'''
'''def p_del(mdl, del_p_name=[],q1_name='', q2_name='', show_G=True, show_par=False):
    
    if (del_p_name==[]) and (q1_name=='' or q2_name==''):
        print('Ведите название линии в del_p_name или названия узлов в q1_name и q2_name')
        return
    if (del_p_name!=[]) and (q1_name!='' or q2_name!=''):
        print('Ведите либо название линии в del_p_name, либо названия узлов в q1_name и q2_name. Не одновременно.')
        return
    submdl=mrtkz.Model() # создаем подрежим
    submdl.Clear()
    submdl=mrtkz.Model()
    q_list = []
    if (del_p_name, tuple): del_p_name = list(del_p_name)
    if not isinstance(del_p_name, list): 
        temp_var = []
        temp_var.append(del_p_name)
        del_p_name = temp_var
    for p in mdl.bp:
        # решаем проблему с тем что узел может быть узлом, а может нулем
        try:        
            q1_p_name = p.q1.name
        except:
            q1 = 0
            q1_p_name = '0'
        try:
            q2_p_name = p.q2.name
        except:
            q2 = 0
            q2_p_name = '0'
        # если это удаляемая ветвь
        if p.name in del_p_name or (q1_p_name == q1_name and  q2_p_name == q2_name) or (q1_p_name == q2_name and  q2_p_name == q1_name):
            if show_par: print('Удаляем ветвь', p.name)
        # для остальных ветвей
        else:
            # создаем узлы, проверяя что они не нулевые и их еще нет в модели (используем для этого список уже добавленных листов)
            if (q1_p_name!='0') and (q1_p_name not in q_list):   
                mrtkz.Q(submdl,name=q1_p_name, x=p.q1.x,y=p.q1.y)
                q_list.append(q1_p_name)

            if (q2_p_name!='0') and (q2_p_name not in q_list):   
                mrtkz.Q(submdl,name=q2_p_name, x=p.q2.x,y=p.q2.y)
                q_list.append(q2_p_name)  
            for q in submdl.bq:
                if q.name == q1_p_name:
                    q1 = q
                if q.name == q2_p_name:
                    q2 = q    
            # добавляем в подрежим ветвь    
            mrtkz.P(submdl,name=p.name,q1=q1,q2=q2,Z=p.Z,E=p.E,T=p.T,B=p.B,desc=p.desc)

            # добавляем в подрежим РЗ
            for q_def in [p.q1_def, p.q2_def]:
                for prot1 in q_def:
                    mrtkz.protection(p=submdl.bp[-1], q=submdl.bp[-1].q1, type=prot1.type, stage=prot1.stage, I0=prot1.I0, t=prot1.t, P_rnm=prot1.P_rnm, rnm_base_angle=prot1.rnm_on, stage_on = prot1.stage_on, I0_range=prot1.I0_range, t_range=prot1.t_range, desc=prot1.desc, k_ch=prot1.k_ch, k_ots=prot1.k_ots, k_voz=prot1.k_voz)
    # добавляем в подрежим взаимоиндукции
    try:
        for m in mdl.bm:
            p1 = p_search(mdl=submdl,p_name=m.p1.name, info=False)
            p2 = p_search(mdl=submdl,p_name=m.p2.name, info=False)
            mrtkz.M(model=submdl,name=m.name,p1=p1,p2=p2,M12=m.M12,M21=m.M21,desc=m.desc)
    except: 1
    # добавляем в подрежим несимметрии
    try:
        for n in mdl.bn:
            mrtkz.N(model=submdl,name=n.name,qp=q_search(submdl,n.qp.name, info=False),SC=n.SC,r=n.r,desc=n.desc)  
    except: 1
    if show_G:
        print_G(submdl)
    return submdl
'''

'''
Визуализация участка энергосистемы (пока только узлы, линии и нулевые узлы)
'''
def print_G(mdl, I=False, show_prot=False):
    if I==False:
        pos = nx.get_node_attributes(mdl.G, 'pos')
        nx.draw(mdl.G, pos, with_labels=True, node_color='lightblue', node_size=500, font_size=10, font_weight='bold')
        edge_labels = nx.get_edge_attributes(mdl.G, 'weight')
        nx.draw_networkx_edge_labels(mdl.G, pos, edge_labels=edge_labels)
    
        #plt.title("Участок энергосистемы")
        plt.axis('off')
        plt.show()
    else:
        """
        Функция визуализирует поток мощности в направленном графе на основе модели 'mdl'.
        Направление тока представлено ориентированными рёбрами, а особые элементы, такие как узлы коротких замыканий,
        генераторы и взаимная индукция, выделены различными цветами и стилями.
        
        Параметры:
        mdl - модель, содержащая информацию о потоках мощности, узлах и соединениях.
        """
        
        mdl.Calc()  # Выполняем расчет параметров модели
        G = mdl.G  # Граф, представляющий модель
        label_dict = {}
        edge_list = []
        node_colors = {}
        mutual_edges_pos = []
    
        # Определение узлов короткого замыкания и их цвет (красный)
        for n in mdl.bn:
            kz_name = n.qp.name
            node_colors[kz_name] = 'red'
    
        # Определение узлов генераторов и их цвет (темно-синий)
        for q in mdl.bp:
            if q.E[0] != 0:
                gen_name = q.name + '_0'
                node_colors[gen_name] = 'darkblue'
    
        # Определение направлений потоков между узлами и добавление ориентированных рёбер
        for p in mdl.bp:
            # Устанавливаем имена для q1 и q2 в зависимости от их наличия
            q1_name = p.q1.name if p.q1 != 0 else p.name + '_0'
            q2_name = p.q2.name if p.q2 != 0 else p.name + '_0'
    
            # Получаем величину и угол тока
            I0 = p.res1(['I0'], 'M')['I0']
            ang = p.res1(['I0'], '<f')['I0']
    
            # Определяем направление ребра в зависимости от угла тока
            if ((-20 <= ang <= 160) or (340 <= ang <= 360)):
                edge = (q1_name, q2_name)
            else:
                edge = (q2_name, q1_name)
            try: I0 = round(I0)
            except: I0=0
            # Подготовка метки для ребра с величиной тока
            line_label = f'{p.name}\nI0={I0}'
            label_dict[edge] = line_label
    
            # Добавляем ориентированное ребро в список рёбер
            edge_list.append(edge)
    
        # Определение линий, связанных взаимной индукцией, и добавление их как тонкие серые линии
        pos = nx.get_node_attributes(mdl.G, 'pos')
        
        for m in mdl.bm:
            # Линии, соединяемые взаимной индукцией
            line1 = m.p1
            line2 = m.p2
            if line1.q1==0: x11 = 0
            else:           x11 = line1.q1.x
            if line1.q2==0: x12 = 0
            else:           x12 = line1.q2.x
            if line1.q1==0: y11 = 0
            else:           y11 = line1.q1.y
            if line1.q2==0: y12 = 0
            else:           y12 = line1.q2.y        
            if line2.q1==0: x21 = 0
            else:           x21 = line2.q1.x
            if line2.q2==0: x22 = 0
            else:           x22 = line2.q2.x
            if line2.q1==0: y21 = 0
            else:           y21 = line2.q1.y
            if line2.q2==0: y22 = 0
            else:           y22 = line2.q2.y

            plt.plot([x11+(x12-x11)/2, x21+(x22-x21)/2], [y11+(y12-y11)/2, x21+(y22-y21)/2], color='gray', linestyle='--', linewidth=1)
            
        # Создаем направленный граф и добавляем рёбра с метками
        directed_G = nx.DiGraph()
        directed_G.add_edges_from(edge_list)
    
        # Устанавливаем метки для рёбер в графе
        nx.set_edge_attributes(directed_G, label_dict, 'label')
    
        # Устанавливаем цвета узлов, по умолчанию светло-голубой
        default_color = 'lightblue'
        node_color_list = [node_colors.get(node, default_color) for node in directed_G.nodes()]
    
        # Рисуем направленный граф с учетом цвета узлов
        nx.draw(directed_G, pos, with_labels=True, node_color=node_color_list, node_size=500, font_size=10, font_weight='bold', arrows=True)
        edge_labels = nx.get_edge_attributes(directed_G, 'label')
        nx.draw_networkx_edge_labels(directed_G, pos, edge_labels=edge_labels, font_size=8, bbox=dict(boxstyle="round", pad=0, edgecolor='none', alpha=0))
    
    
            
    
        #plt.title("Участок энергосистемы")
        plt.axis('off')
        plt.show()

        if show_prot:
            for p in mdl.bp:
                if p.q1!=0:
                    lable = f'{p.name}, {p.q1.name}:'
                    #if (30 - len(lable))>0:
                    space = '_'*(20 - len(lable))
                    lable += space
                    row = ''
                    for d in p.q1_def:
                        row += f'Ст.{d.stage} I0={round(d.I0)}, t={round(d.t,1)}|'
                    print(lable+row)
                if p.q2!=0:
                    lable = f'{p.name}, {p.q2.name}:'
                    space = '_'*(20 - len(lable))
                    lable += space
                    row = ''
                    for d in p.q2_def:
                        row += f'Ст.{d.stage} I0={round(d.I0)}, t={round(d.t,1)}|'
                    print(lable+row)





# функция, каходящая линию по названию узлов или ветви в модели
def p_search(mdl,q1='',q2='', p_name='', info=True):
    line = ''
    # Поиск по названию ветви
    if p_name!='' and q1=='' and q2=='':
        for p in mdl.bp:
            if p.name==p_name: line = p
     # Поиск по названию ветвей
    elif q1!='' and q2!='' and p_name=='':
        for p in mdl.bp:
            try:    q1p = p.q1.name
            except: q1p = 0
            try:    q2p = p.q2.name
            except: q2p = 0
            if (q1p==q1 and q2p==q2) or (q1p==q2 and q2p==q1):
                line = p
    else: print('Необходимо искаль либо по узлам, либо по названию')
    if  line=='' and info: print('Линия не найдена',p_name)

    return line

# функция, находящая узел по названию
def q_search(mdl,q_name='', info=True):
    q_ser = ''
    for q in mdl.bq:
        if q.name==q_name: q_ser = q
    if q=='' and info: print('Введите название узла')
    #if  line=='': print('Линия не найдена')

    return q_ser




# функция создает новую модель и другие объекты на основании другой модели
def duplicate_mdl(mdl1, show_G = False):
    mdl2=mrtkz.Model()
    q_list = []
    for p in mdl1.bp:
         # решаем проблему с тем что узел может быть узлом, а может нулем
        try:        
            q1_p_name = p.q1.name
        except:
            q1 = 0
            q1_p_name = '0'
        try:
            q2_p_name = p.q2.name
        except:
            q2 = 0
            q2_p_name = '0'
        # создаем узлы, проверяя что они не нулевые и их еще нет в модели (используем для этого список уже добавленных листов)
        if (q1_p_name!='0') and (q1_p_name not in q_list):   
            mrtkz.Q(mdl2,name=q1_p_name, x=p.q1.x,y=p.q1.y)
            q_list.append(q1_p_name)

        if (q2_p_name!='0') and (q2_p_name not in q_list):   
            mrtkz.Q(mdl2,name=q2_p_name, x=p.q2.x,y=p.q2.y)
            q_list.append(q2_p_name)  
        for q in mdl2.bq:
            if q.name == q1_p_name:
                q1 = q
            if q.name == q2_p_name:
                q2 = q    
        # добавляем в подрежим ветвь    
        mrtkz.P(mdl2,name=p.name,q1=q1,q2=q2,Z=p.Z,E=p.E,T=p.T,B=p.B,desc=p.desc)
        #self.nq1_def = 0
        #self.nq2_def = 0
        #mdl.bp[3].q1_def[0].type
        for prot1 in p.q1_def:
            mrtkz.protection(p=mdl2.bp[-1], q=mdl2.bp[-1].q1, stat_id=prot1.stat_id, type=prot1.type, stage=prot1.stage, I0=prot1.I0, t=prot1.t, P_rnm=prot1.P_rnm, rnm_base_angle=prot1.rnm_on, stage_on = prot1.stage_on, I0_range=prot1.I0_range, t_range=prot1.t_range, desc=prot1.desc, k_ch=prot1.k_ch, k_ots=prot1.k_ots, k_voz=prot1.k_voz)
        
        for prot1 in p.q2_def:
            mrtkz.protection(p=mdl2.bp[-1], q=mdl2.bp[-1].q2, stat_id=prot1.stat_id, type=prot1.type, stage=prot1.stage, I0=prot1.I0, t=prot1.t, P_rnm=prot1.P_rnm, rnm_base_angle=prot1.rnm_on, stage_on = prot1.stage_on, I0_range=prot1.I0_range, t_range=prot1.t_range, desc=prot1.desc, k_ch=prot1.k_ch, k_ots=prot1.k_ots, k_voz=prot1.k_voz)

    # добавляем в подрежим взаимоиндукции
    for m in mdl1.bm:
        p1 = p_search(mdl=mdl2,p_name=m.p1.name)
        p2 = p_search(mdl=mdl2,p_name=m.p2.name)
        mrtkz.M(model=mdl2,name=m.name,p1=p1,p2=p2,M12=m.M12,M21=m.M21,desc=m.desc)
    # добавляем в подрежим несимметрии
    for n in mdl1.bn:
        mrtkz.N(model=mdl2,name=n.name,qp=q_search(mdl2,n.qp.name),SC=n.SC,r=n.r,desc=n.desc)

    if show_G:
        print_G(mdl2)
    return mdl2


# функция берет общий df с результатами, линию из функции промКЗ, долю линии% в которой от узла q1 произошло КЗ, и линию в которой результат.
# возвращает df с результатами по концам этой линии
'''
results_df = pd.DataFrame(columns = ['Линия кз', 'Место кз', 'Тип кз', 'Линия', 'Узел','U1','U2','U0','3U0','UA','UB','UC','UAB','UBC','UCA',
        'I1','I2','I0','3I0','IA','IB','IC','IAB','IBC','ICA',
        'Z1','Z2','Z0','ZA','ZB','ZC','ZAB','ZBC','ZCA',
        'S1','S2','S0','SA','SB','SC','SAB','SBC','SCA','S'])

full_p_var_list = ['U1','U2','U0','3U0','UA','UB','UC','UAB','UBC','UCA',
        'I1','I2','I0','3I0','IA','IB','IC','IAB','IBC','ICA',
        'Z1','Z2','Z0','ZA','ZB','ZC','ZAB','ZBC','ZCA',
        'S1','S2','S0','SA','SB','SC','SAB','SBC','SCA','S']
'''

# возвращает одну строку датафрейма ТКЗ
# выводит результаты в виде датафрейма
def add_line_results(results_df=0, KZ_type='Тип КЗ', line_of_query='объект линии данные которого выписываются' , line="название линии на которой происходит кз", percentage_of_line=0.5, var_list=['U1','U2','U0','3U0','UA','UB','UC','UAB','UBC','UCA','I1','I2','I0','3I0','IA','IB','IC','IAB','IBC','ICA','Z1','Z2','Z0','ZA','ZB','ZC','ZAB','ZBC','ZCA','S1','S2','S0','SA','SB','SC','SAB','SBC','SCA','S'], kaskade=0, p_off=('Полный режим',)):
    j=0
    vars12 = []
    q12=line_q_names(line_of_query) # выводим ненулевые имена узлов линии
    
    # создаем подсловари по двум узлам 
    try:
        q1 = line_of_query.q1.name
        vars1 = {} 
        vars1['Узел'] = q1
        vars1.update(line_of_query.res1(parnames=var_list)) 
        vars12.append(vars1)
        j = j+1
    except: 1
        
    try:
        q2 = line_of_query.q2.name
        vars2 = {} 
        vars2['Узел'] = q2
        vars2.update(line_of_query.res2(parnames=var_list)) 
        vars12.append(vars2)
        j = j+1
    except: 1
    
    for i in range(j):
        # создаем словари с общими столбцами
        vars = {}
        vars['Линия кз'] = line
        vars['Место кз'] = percentage_of_line
        vars['Тип кз'] = KZ_type
        vars['Линия'] = line_of_query.name
        vars['Каскад'] = kaskade
        vars['Отключенные ветви'] = [p_off]        
        
        # добавляем к ним столбцы выше и переводим это все в DF
        vars2_lists = {}
        for k, v in vars12[i].items():
            # Если значение это np.array с комплексными числами
            if isinstance(v, np.ndarray) and np.iscomplexobj(v):
                # Найдем и заменим "nan + nanj" на "0 + 0j"
                mask = np.isnan(v.real) & np.isnan(v.imag)
                v[mask] = 0 + 0j
            # Добавляем в словарь
            vars2_lists[k] = [v]
    
        # Обновляем исходный словарь
        vars.update(vars2_lists)
    
        # Создаем DataFrame
        df_vars = pd.DataFrame(vars)

        '''
        print(df_vars)
        
        
        vars2_lists = {k: [v] for k, v in vars12[i].items()}
        
        vars.update(vars2_lists)
        
        df_vars = pd.DataFrame(vars)
        '''
        # добавляем к результирующему DF
        try:
            results_df = pd.concat([results_df, df_vars])
        except: 
            full_var_list = ['Линия кз', 'Место кз', 'Тип кз', 'Линия', 'Узел', 'Каскад', 'Отключенные ветви'] + var_list
            results_df = pd.DataFrame(columns = full_var_list) # создаем DF в который будут выводиться результаты
            results_df = pd.concat([results_df, df_vars])
        i+=1
        
    return results_df
    

# возвращает названия узлов линии, не ломаясь об нули
def line_q_names(line):
    try:    q1 = line.q1.name
    except: q1 = 0 
    try:    q2 = line.q1.name
    except: q2 = 0
    return [q1, q2]


# Функция выводит датафрейм из защит модели
def def_to_df(mdl):
    df_result = pd.DataFrame()
    for p in mdl.bp:
        for q in [p.q1_def, p.q2_def]:
            for d in q:
                def_par = {}
                vars = {}
                def_par['prot_id'] = d.id
                def_par['Линия'] = p.name
                try: def_par['узел'] = d.q.name
                except: def_par['узел'] = '0'
                def_par['тип РЗ'] = d.type
                def_par['№ ступени'] = d.stage
                def_par['I0_сраб'] = d.I0
                def_par['t_сраб'] = d.t
                def_par['Введена ли защита'] = d.stage_on
                def_par['мощность сраб РНМ'] = d.P_rnm
                def_par['Введена ли РНМ'] = d.rnm_on
                def_par['Угол РНМ'] = d.rnm_ang
                def_par['Kч'] = d.k_ch
                def_par['Котс'] = d.k_ots
                def_par['Кв'] = d.k_voz

                def_par_lists = {k: [v] for k, v in def_par.items()}
                vars.update(def_par_lists)
                df_res = pd.DataFrame(vars)
                df_result = pd.concat([df_result, df_res], ignore_index=True)

    return df_result




# Функция для составления словаря удаленности линий и узлов от данной линиии
'''
mdl - подель поиска
line - линия от которой отсчитывается расстояние
n - максимальное расстояние поиска от узла
return_names - если True возвращет имена линий, вместо объектов

Функция возвращает 2 словаря
словарь линий с ключами равными номеру пояса и значениями, равными списку линий
аналогичный словарь узлов
'''
def belt_search(mdl, line, n, return_names=False):
    p_range_dict = {i: set() for i in range(1, n+1)}
    q_range_dict = {i: set() for i in range(1, n+1)}
    
    p_range_dict['line'] = line.name
    q_range_dict['line'] = line.name

    queue = deque([(line, 0)])
    visited_p = set([line])
    visited_q = set()

    while queue:
        current_p, level = queue.popleft()
        
        if level >= n:
            break

        for q in [current_p.q1, current_p.q2]:
            if q != 0 and q not in visited_q:
                visited_q.add(q)
                q_range_dict[level + 1].add(q)
                for next_p in q.plist:
                    if next_p not in visited_p:
                        visited_p.add(next_p)
                        p_range_dict[level + 1].add(next_p)
                        if level + 1 < n:
                            queue.append((next_p, level + 1))

    # Удаляем исходную линию из первого уровня
    p_range_dict[1].discard(line)
    
    if return_names:
        # Преобразуем объекты в их имена если параметр return_names = True
        p_range_dict_names = {k: {p.name for p in v} if isinstance(k, int) else v 
                              for k, v in p_range_dict.items()}
        q_range_dict_names = {k: {q.name for q in v} if isinstance(k, int) else v 
                              for k, v in q_range_dict.items()}
        return p_range_dict_names, q_range_dict_names
    else:
        return p_range_dict, q_range_dict
'''
# Пример использования:
mdl = mdl  # ваша модель
line = mdl.bp[2]  # выбранная линия
n = 3  # радиус поиска

p_range_dict, q_range_dict = optimized_search(mdl, line, n)
'''



# создает списки линий перебирая все линии в словаре, в наборами по m едениц 
'''
p_range_dict - словарь линий из предыдущей функции
m - количество линий в переборе 

show_info - выводит информацию о кол-ве линий и вариантов перебора
return_as_list - выводит списом, если правда и объектом перебоа, если ложь
belts_list - список поясов, если нужны не все а только выборочные (напр [0,2])
'''
def generate_line_combinations(p_range_dict, m, show_info=True, return_as_list=False, belts_list = ''):
    all_lines = set()  # Используем множество для уникальности
    
    # вписываем в единую строку те, что есть в belts_list, если он не пустой
    for level, lines in p_range_dict.items():
        if isinstance(level, int):
            if belts_list != '':
                if level in belts_list:
                    all_lines.update(lines)
            else: all_lines.update(lines)
    
    all_lines = list(all_lines)  # Преобразуем обратно в список
    combinations = list(itertools.combinations(all_lines, m))  # Создаем список комбинаций
    if show_info:
        print(f"Всего линий: {len(all_lines)}")
        print(f"Количество комбинаций: {len(combinations)}")
    if return_as_list: combinations = list(combinations)
        
    return combinations



# Функция получающая на вход пояс перебора и количество линий в переборе, и возвращающая список вариантов списов линий
''' функция объеденияет предыдущие две'''
def line_enumiration(mdl, line, max_belt_range, num_of_enum_lines, list_of_belts_for_enum='', return_names=False, show_info=True, return_as_list=True):    
    p = belt_search(mdl=mdl, line=line, n=max_belt_range, return_names=return_names)[0]
    cmbinations = generate_line_combinations(p_range_dict=p, m=num_of_enum_lines, show_info=show_info, return_as_list=return_as_list, belts_list=list_of_belts_for_enum)
    return cmbinations


# создает df по подрежиму
def q_kz_p_del_mdl(mdl, line, p_off, percentage_of_line, KZ_type, var_list, show_G=False):
    results_df = 0
    # Создание подмодели с определенными параметрами
    submdl = kz_q(mdl, line, percentage_of_line=percentage_of_line, show_G=False, show_par=False, kaskade=False)
    submdl = p_del(submdl, del_p_name=p_off, show_G=show_G, show_par=False)
    # Выполнение расчетов для подмодели
    KZ1 = mrtkz.N(submdl, 'KZ', submdl.bq[-1], KZ_type)
    # Запуск расчетов подмодели
    submdl.Calc()
    # Добавление результатов в DataFrame
    for p in submdl.bp:
        results_df = add_line_results(results_df=results_df, 
                                           KZ_type=KZ_type, 
                                           line_of_query=p, 
                                           line=line.name, 
                                           percentage_of_line=percentage_of_line, 
                                           var_list=var_list, 
                                           kaskade=0, 
                                           p_off=p_off)
    # Выполнение запроса на отбор данных по определенной линии
    results_df.loc[results_df['Линия'] == line.name]
    return results_df

# создает подрежим, считает его и возвращает результаты по строке df base_df
def df_row_calc_df(base_mdl, base_df_row, show_G=False):
    line = p_search(mdl, p_name=base_df_row['Линия кз'][0])
    p_off = base_df_row['Отключенные ветви'][0]
    percentage_of_line = base_df_row['Место кз'][0]
    KZ_type = base_df_row['Тип кз'][0]
    var_list = [item for item in base_df_row.columns if item not in ['Линия кз', 'Место кз', 'Тип кз', 'Линия', 'Узел', 'Каскад', 'Отключенные ветви']]
    res_df = q_kz_p_del_mdl(mdl=mdl, line=mdl.bp[2], p_off=('Sys2','PS1-PS3',), percentage_of_line=0.5, KZ_type='A0', var_list=['I0','S0'], show_G=True)
    return res_df
























# Анализ защит дальн рез когда починю рассчет токов, добавить рассчет токов кз
# нужно добавить ограничение анализа узлов, хотя лучше его добавить в функции таблицы ткз и достройки режима внутри функции

import pandas as pd
import numpy as np
import cmath



def check_rnm_df(df_row):
    I0 = df_row['I0'].values[0]
    U0 = df_row['U0'].values[0]
    S0 = U0 * np.conj(I0)
    S0_angle = cmath.phase(S0) * 180 / np.pi
    angle_diff = abs((S0_angle - df_row['угол макс РНМ'] + 180) % 360 - 180)
    
    if angle_diff > 90:
        return False
    
    if abs(S0) <= df_row['мощность сраб РНМ'] / np.cos(np.radians(angle_diff)):
        return False
    return True
    
def analyze_remote_backup_protection(mdl, def_df, base_df, line_kz, print_log = False):
    # Создаем DataFrame для хранения результатов анализа
    results = pd.DataFrame(columns=['Линия КЗ', 'Тип КЗ', 'Место КЗ', 'Сработавшая защита', 
                                'Ступень защиты', 'Ток срабатывания', 'Ток КЗ', 'Время срабатывания', 'Отключенные линии', 'Группа отключения', 'Пояс'])
    
    # Перебираем все уникальные комбинации типа КЗ, места КЗ и отключенных ветвей для заданной линии КЗ
    for (kz_type, kz_percent, kz_off_lines), kz_group in base_df[base_df['Линия кз'] == line_kz].groupby(['Тип кз', 'Место кз', 'Отключенные ветви']):
        kz_off_lines = kz_off_lines
        j=0
        past_total_time = 0
        total_time = 0
        tripped_lines = set()
        current_data = kz_group
        
        # Определяем узлы линии КЗ и список линий первого пояса
        kz_q12 = base_df.loc[(base_df['Линия']==line_kz)]['Узел'].unique()
        kz_1_belt_lines_list = base_df.loc[base_df['Узел'].isin(kz_q12)]['Линия'].unique()
        belt_lines_count = len(kz_1_belt_lines_list)


        kz_q12 = base_df.loc[(base_df['Линия']==line_kz)]['Узел'].unique()
        kz_1_belt_lines_list = base_df.loc[base_df['Узел'].isin(kz_q12)]['Линия'].unique()
        elements_to_remove = ['q1-kz', 'kz-q2', line_kz]
        kz_1_belt_lines_tuple = (tuple(item for item in kz_1_belt_lines_list if item not in elements_to_remove))

        
        if print_log: print(f"Анализ КЗ: Линия {line_kz}, Тип {kz_type}, Место {kz_percent}, Отключенные ветви {kz_off_lines}")
        
        # Выбираем все активные защиты, кроме защит линии КЗ, и сортируем их по времени срабатывания
        all_protections = def_df[(def_df['Введена ли защита'] == True) & (def_df['Линия'] != line_kz)].sort_values('t_сраб')
        all_protections['Времени до срабатывания'] = all_protections['t_сраб']        
        all_protections['Сработала'] = False  
        all_protections.reset_index(drop=True, inplace=True)        
        off_lines = kz_off_lines
        distant_belts_off_lines = []
        while True:
            all_protections['Почувствовала'] = False   
            off = False
            if current_data.empty:
                if print_log: print("Нет данных для анализа")
                break
                
            past_total_time = total_time
            
            j+=1
            i=-1
            # Проверяем каждую защиту
            for _, prot in all_protections.iterrows():
                temp_off_lines = ()
                i+=1
                line = prot['Линия']
                node = prot['узел']
                
                # Пропускаем уже отключенные линии
                if line in off_lines or line in distant_belts_off_lines:
                    #print('Пропущена защита', line)
                    continue
                
                # Находим соответствующую строку данных для текущей защиты
                row = current_data[(current_data['Линия'] == line) & (current_data['Узел'] == node)]
                
                if row.empty:
                    continue
                
                # Извлекаем значения тока и мощности
                I0 = complex(row['I0'].values[0])
                S0 = complex(row['S0'].values[0])
                
                protection_key = f"{line}|{node}-{prot['№ ступени']}"
                
                # Проверяем условие срабатывания РНМ, если оно введено
                rnm_check_passed = True
                if prot['Введена ли РНМ']:
                    rnm_check_passed = check_rnm_I_df(row, prot)#check_rnm(S0, prot['мощность сраб РНМ'], prot['угол РНМ'])
                    
                if rnm_check_passed:
                    # Вычисляем уставки по току с учетом коэффициентов чувствительности и отстройки
                    Kch_I0 = prot['I0_сраб']/prot['Kч']
                    Kots_I0 = prot['I0_сраб']/prot['Котс']
                    
                    # Проверяем условия срабатывания защиты
                    if line in kz_1_belt_lines_tuple and abs(I0) > Kch_I0 or line not in kz_1_belt_lines_tuple and abs(I0) > Kots_I0:
                        #prot['Почувствовала']=True
                        all_protections.loc[i,'Почувствовала'] = True
                        #print(protection_key)
                    elif abs(I0) <= prot['I0_сраб']*prot['Кв']:
                        #prot['Времени до срабатывания'] = prot['t_сраб']
                        all_protections.loc[i,'Времени до срабатывания']= prot['t_сраб']
                    # Здесь нужно добавить логику для обработки protection_start_times
                    # if protection_key not in protection_start_times:
                    #     protection_start_times[protection_key] = total_time
                else:
                    prot['Времени до срабатывания'] = prot['t_сраб']
                    #prot['Времени до срабатывания'] = prot['t_сраб']
                    all_protections.loc[i,'Времени до срабатывания']= prot['t_сраб']
            # Сортируем защиты по времени срабатывания
            all_protections = all_protections.sort_values(by='Времени до срабатывания')
            # Находим время срабатывания ближайшей защиты первого пояса
            #a = all_protections.loc[all_protections['Почувствовала']].count()[0]
            #print('ПОЧУВСТВ',a)
            
            try:
                total_time = all_protections.loc[(all_protections['Линия'].isin(kz_1_belt_lines_tuple)) & (all_protections['Почувствовала'])].head(1)['Времени до срабатывания'].values[0]
            except:
                try: belt = row['Пояс'].values[0]
                except: belt = 4
                new_result = pd.DataFrame({
                        'Линия КЗ': [line_kz],
                        'Тип КЗ': [kz_type],
                        'Место КЗ': [kz_percent],
                        'Сработавшая защита': [f"Защиты не чувствуют"],
                        'Ступень защиты': [0],
                        'Ток срабатывания': [0],
                        'Ток КЗ': [0],
                        'Время срабатывания': [total_time],
                        'Отключенные линии': [off_lines],
                        'Группа отключения': [j],
                        'Пояс': [belt] })
                if print_log: print(f"КЗ не отключено:{temp_off_lines} ")
                results = pd.concat([results, new_result], ignore_index=True)
                off = True      
            
            if off == True:
                break
            # Отмечаем сработавшие защиты
            distant_belts_off_lines += all_protections.loc[(all_protections['Времени до срабатывания'] <= total_time) & (all_protections['Почувствовала']),'Линия'].unique().tolist()
            # Выделяем сработавшие защиты в отдельный DataFrame
            worked_protections = all_protections.loc[(all_protections['Времени до срабатывания'] <= total_time) & (all_protections['Почувствовала'])]
            # Уменьшаем время до срабатывания для оставшихся активных защит
            all_protections.loc[(all_protections['Времени до срабатывания'] > total_time) & (all_protections['Почувствовала']), 'Времени до срабатывания'] -= total_time
            
           
            
            
            # Записываем результаты сработавших защит
            for _, protection in worked_protections.iterrows():
                line = protection['Линия']
                node = protection['узел']
                row = current_data[(current_data['Линия'] == line) & (current_data['Узел'] == node)]
                try: belt = row['Пояс'].values[0]
                except: belt = 4
                #print(row['I0'])
                try: I0 = complex(row['I0'].values[0])
                except: I0 = 0
                trip_time = past_total_time + protection['Времени до срабатывания']

                new_result = pd.DataFrame({
                            'Линия КЗ': [line_kz],
                            'Тип КЗ': [kz_type],
                            'Место КЗ': [kz_percent],
                            'Сработавшая защита': [f"{line} | {node}"],
                            'Ступень защиты': [protection['№ ступени']],
                            'Ток срабатывания': [protection['I0_сраб']],
                            'Ток КЗ': [abs(I0)],
                            'Время срабатывания': [trip_time],
                            'Отключенные линии': [off_lines],
                            'Группа отключения': [j],
                            'Пояс': [belt] })
                results = pd.concat([results, new_result], ignore_index=True)
                #print(f"Сработала защита: {line} | {node}, время: {trip_time}")
                
                # Если сработавшая защита относится к линии первого пояса, записываем ее
                if line in kz_1_belt_lines_tuple:
                    temp_off_lines += (line,)
                    temp_off_lines = tuple(temp_off_lines)
                    belt_lines_count -= 1
                    if print_log: print(f"Отключены линии: {line}, время: {total_time}, линий осталось {belt_lines_count}")

            if print_log: print(f"Отключены линии:{temp_off_lines} за шаг {j}")

            #  Добавляем отключенные за этот шаг линии к отключенным и меняем подрежим
            off_lines = tuple(off_lines) + temp_off_lines
            if print_log: print(f"Отключен линии ВСЕГО:{off_lines} за шаг {j}")
            belt_lines_count -= 1
            # Переходим к новому подрежиму после отключения линий
            line_kz_obj = p_search(mdl, p_name=line_kz)
            var_list = [item for item in base_df.columns if item not in ['Линия кз', 'Место кз', 'Тип кз', 'Линия', 'Узел', 'Каскад', 'Отключенные ветви']]
            current_data = q_kz_p_del_mdl(mdl=mdl, line=line_kz_obj, p_off=off_lines, percentage_of_line=kz_percent, KZ_type=kz_type, var_list=['I0','S0'], show_G=False)

                    
            
            #print(kz_line_data)
            # Проверяем условия завершения анализа
            kz_line_data = current_data[current_data['Линия'].isin(["kz-q2", "q1-kz"])]
            kz_line_data['I0'] = kz_line_data['I0'].apply(lambda x: complex(x) if isinstance(x, str) else x)    
            
            if all(item in off_lines for item in kz_1_belt_lines_tuple):
                if print_log: print("Все линии первого пояса отключены")
                if print_log: print(f"Всего строк в результате: {len(results)}")               
                break
                

            elif (all(abs(kz_line_data['I0']) < 1e-6)): #and all(abs(kz_line_data['S0']) < 1e-6)):
                if print_log: print("Ток и напряжение в обоих узлах линии КЗ стали нулевыми")
                if print_log: print(f"Всего строк в результате: {len(results)}")               
                break
            
    return results
'''
# Пример использования функции
base_df.reset_index(drop=True, inplace=True) 
def_df.reset_index(drop=True, inplace=True) 
#result_df = analyze_remote_backup_protection(mdl, def_df, base_df, 'PS1-PS2')
#print(result_df)
'''



def I3f_ots(mdl, line):
    """
    Выполняет расчет токов нулевой последовательности в линии при 
    трехфазном коротком замыкании в точках q1 и q2.

    Параметры:
    mdl : object
        Модель системы, на которой выполняется расчет.
    line : object
        Линия, для которой производится расчет токов.

    Возвращает:
    tuple : (q1_IA, q2_IA)
        q1_IA : float
            Абсолютное значение тока в точке q1.
        q2_IA : float
            Абсолютное значение тока в точке q2.
    """
    # Создаем дубликат модели для проведения расчетов
    submdl = duplicate_mdl(mdl)
    # Находим линию в модели по её имени
    line = p_search(submdl, p_name=line.name)
    try:     
        # Создаем 3-фазное короткое замыкание на конце q1 линии
        KZ1 = mrtkz.N(submdl, 'KZ1', line.q1, 'ABC')
        # Выполняем расчет токов в модели
        submdl.Calc()
        # Извлекаем имя узла q1 и значение тока IA в узле q1
        q1_name = line.q1.name
        q1_IA = abs(line.res1(parnames=['IA'])['IA'])
    except: 
        # Если произошла ошибка, устанавливаем ток в 0
        q1_IA = 0
    
    # Создаем новый дубликат модели для проведения второго расчета
    submdl = duplicate_mdl(mdl)
    # Находим линию в модели по её имени
    line = p_search(submdl, p_name=line.name)
    try:    
        # Создаем 3-фазное короткое замыкание на конце q2 линии
        KZ1 = mrtkz.N(submdl, 'KZ1', line.q2, 'ABC')
        # Выполняем расчет токов в модели
        submdl.Calc()
        # Извлекаем имя узла q2 и значение тока IA в узле q2
        q2_name = line.q2.name
        q2_IA = abs(line.res1(parnames=['IA'])['IA'])
    except: 
        # Если произошла ошибка, устанавливаем ток в 0
        q2_IA = 0
    
    # Возвращаем значения токов для узлов q1 и q2
    return q1_IA, q2_IA

def kz_3f_ots_to_result_df(mdl, base_df, def_df, print_log=False):
    """
    Выполняет анализ срабатывания защит при трехфазных коротких замыканиях
    и возвращает результаты в виде DataFrame.

    Параметры:
    mdl : object
        Модель системы, на которой выполняется анализ.
    base_df : DataFrame
        Базовый DataFrame, содержащий информацию об отключениях линий.
    def_df : DataFrame
        DataFrame с параметрами защит, которые необходимо проверить.
    print_log : bool, optional
        Если True, выводит в лог промежуточные результаты (по умолчанию False).

    Возвращает:
    DataFrame
        DataFrame с результатами срабатывания защит, содержащий следующие столбцы:
        - 'Линия КЗ': Линия, на которой произошло КЗ.
        - 'Тип КЗ': Тип КЗ (в данном случае 'Отстройка от 3ф кз').
        - 'Место КЗ': Процент КЗ относительно длины линии.
        - 'Сработавшая защита': Описание сработавшей защиты.
        - 'Ступень защиты': Номер ступени защиты.
        - 'Ток срабатывания': Ток, при котором сработала защита.
        - 'Ток КЗ': Вычисленный ток короткого замыкания.
        - 'Время срабатывания': Время срабатывания защиты.
        - 'Отключенные линии': Ветви, отключенные при анализе.
        - 'Группа отключения': Группа отключения (в данном случае всегда 0).
    """
    
    # Создаем пустой DataFrame для хранения результатов
    results = pd.DataFrame(columns=['Линия КЗ', 'Тип КЗ', 'Место КЗ', 'Сработавшая защита', 
                                    'Ступень защиты', 'Ток срабатывания', 'Ток КЗ', 
                                    'Время срабатывания', 'Отключенные линии', 'Группа отключения', 'Пояс']) 
    
    # Перебираем все линии в модели
    for line in mdl.bp:
        try: 
            # Пытаемся получить узел q1 для линии
            q1 = line.q1
        except: 
            # Если ошибка, устанавливаем q1 в '0'
            q1 = '0'
        
        try: 
            # Пытаемся получить узел q2 для линии
            q2 = line.q2
        except: 
            # Если ошибка, устанавливаем q2 в '0'
            q2 = '0'
        
        # Получаем уникальные комбинации отключенных ветвей для текущей линии КЗ
        submdls_lines_off = base_df.loc[base_df['Линия кз'] == line.name, 'Отключенные ветви'].unique()
        
        # Перебираем все комбинации отключенных ветвей
        for del_p_tuple in submdls_lines_off:
            # Создаем подмодель с отключенными ветвями
            submdl = p_del(mdl=mdl, del_p_name=del_p_tuple, show_G=False, show_par=False)
            # Вычисляем токи в узлах q1 и q2 для этой подмодели
            I12, I21 = I3f_ots(submdl, line)
    
            # Фильтруем защитные устройства, которые привязаны к данной линии и имеют время срабатывания <= 1 с
            temp_def = def_df.loc[(def_df["Линия"] == line.name) & (def_df["t_сраб"] <= 1)]
            
            # Перебираем каждое защитное устройство
            for _, prot in temp_def.iterrows():
                # Устанавливаем начальное значение коэффициента нагрузки блока (knb)
                knb = 0.07
                # Получаем узел, в котором установлено защитное устройство
                node = prot['узел']
                # Получаем время срабатывания защитного устройства
                t = prot["t_сраб"]
                
                # Определяем коэффициент чувствительности от времени срабатывания
                if t <= 0.1:
                    kper = 2
                elif t < 0.5:
                    kper = 1.5
                else:
                    kper = 1
                
                # Проверяем, введена ли защита от несимметричных токов
                if prot['Введена ли РНМ']:
                    if node == q1:
                        # Если узел защиты совпадает с узлом q1, берем ток I21 и устанавливаем процент КЗ в 1
                        I = I21
                        kz_percent = 1
                    if prot['узел'] == q2:
                        # Если узел защиты совпадает с узлом q2, берем ток I12 и устанавливаем процент КЗ в 0
                        I = I12
                        kz_percent = 0
                else:
                    # Если защита от несимметричных токов не введена, берем максимальный ток и устанавливаем процент КЗ в 0
                    I = max(I12, I21)
                    kz_percent = 0
                
                # Вычисляем ток срабатывания защиты с учетом коэффициентов
                Iots = prot['Котс'] * kper * I * knb
                if print_log: 
                    # Логируем значения токов для отладки, если включен флаг print_log
                    print(Iots, I21, I21)
                
                # Проверяем, превышает ли вычисленный ток ток срабатывания защиты
                if Iots >= prot['I0_сраб']:
                    if print_log: 
                        # Логируем факт срабатывания защиты, если включен флаг print_log
                        print('Сработала')
                    
                    # Формируем запись о срабатывании защиты
                    new_result = pd.DataFrame({
                        'Линия КЗ': [line.name],
                        'Тип КЗ': ['Отстройка от 3ф кз'],
                        'Место КЗ': [kz_percent],
                        'Сработавшая защита': [f"{line.name} - {node}"],
                        'Ступень защиты': [prot['№ ступени']],
                        'Ток срабатывания': [prot['I0_сраб']],
                        'Ток КЗ': [Iots],
                        'Время срабатывания': [prot['t_сраб']],
                        'Отключенные линии': [del_p_tuple],
                        'Группа отключения': [0],
                        'Пояс': [10] })
                    
                    # Добавляем новую запись в результирующий DataFrame
                    results = pd.concat([results, new_result], ignore_index=True)        
    
    # Возвращаем результирующий DataFrame с информацией о срабатывании защит
    return results










# ближнее резервирование, как я устал его делать

#                                                         ИТОГ

import pandas as pd
import numpy as np
import cmath



def check_rnm_I_df(row, prot):
    I0 = row['I0'].values[0]
    S0 = row['S0'].values[0]
    S0_angle = cmath.phase(S0) * 180 / np.pi
    angle_diff = abs((S0_angle - prot['угол макс РНМ'] + 180) % 360 - 180)
    
    if angle_diff > 90:
        return False
    
    if abs(S0) <= prot['мощность сраб РНМ'] / np.cos(np.radians(angle_diff)):
        return False
    return True
    
def analyze_I_protection(mdl, def_df, base_df, line_kz, print_log = False):
    # Создаем DataFrame для хранения результатов анализа
    results = pd.DataFrame(columns=['Линия КЗ', 'Тип КЗ', 'Место КЗ', 'Сработавшая защита', 
                                'Ступень защиты', 'Ток срабатывания', 'Ток КЗ', 'Время срабатывания', 'Отключенные линии', 'Группа отключения', 'Пояс'])
    
    # Перебираем все уникальные комбинации типа КЗ, места КЗ и отключенных ветвей для заданной линии КЗ
    for (kz_type, kz_percent, kz_off_lines), kz_group in base_df[base_df['Линия кз'] == line_kz].groupby(['Тип кз', 'Место кз', 'Отключенные ветви']):
        j=0
        past_total_time = 0
        total_time = 0
        tripped_lines = set()
        current_data = kz_group.loc[kz_group['Каскад']==0]
        try: q1_name = p_search(mdl=mdl,p_name=line_kz).q1.name
        except: q1_name = '0'
        try: q2_name = p_search(mdl=mdl,p_name=line_kz).q2.name
        except: q2_name = '0'             
        q1_off = False
        q2_off = False
        
        # Определяем узлы линии КЗ и список линий первого пояса
        #kz_q12 = base_df.loc[(base_df['Линия']==line_kz)]['Узел'].unique()
        #kz_1_belt_lines_list = base_df.loc[base_df['Узел'].isin(kz_q12)]['Линия'].unique()
        #belt_lines_count = len(kz_1_belt_lines_list)


        kz_q12 = base_df.loc[(base_df['Линия']==line_kz)]['Узел'].unique()
        #kz_1_belt_lines_list = base_df.loc[base_df['Узел'].isin(kz_q12)]['Линия'].unique()
        elements_to_remove = ['q1-kz', 'kz-q2', line_kz]
        #kz_1_belt_lines_tuple = (tuple(item for item in kz_1_belt_lines_list if item not in elements_to_remove))
        
        
        if print_log: print(f"Анализ КЗ: Линия {line_kz}, Тип {kz_type}, Место {kz_percent}, Отключенные ветви {kz_off_lines}")
        
        # Выбираем все активные защиты, и сортируем их по времени срабатывания
        all_protections = def_df[(def_df['Введена ли защита'] == True)].sort_values('t_сраб')
        all_protections['Времени до срабатывания'] = all_protections['t_сраб']        
        all_protections['Сработала'] = False  
        all_protections.reset_index(drop=True, inplace=True)        
        off_lines = kz_off_lines
        distant_belts_off_lines = []
        while True:
            
            all_protections['Почувствовала'] = False   
            off = False
            if current_data.empty:
                if print_log: print("Нет данных для анализа")
                break
                
            past_total_time = total_time
            
            j+=1
            i=-1
            # Проверяем каждую защиту
            for _, prot in all_protections.iterrows():
                test_print=False
                temp_off_lines = ()
                i+=1
                line = prot['Линия']
                node = prot['узел']
                # Пропускаем уже отключенные линии
                if line in distant_belts_off_lines:
                    continue
                if line == line_kz and node == q1_name and q1_off==True:
                    continue
                if line == line_kz and node == q2_name and q2_off==True:
                    continue    
                # Находим соответствующую строку данных для текущей защиты
                if line == line_kz and node == q1_name and q1_off==False:
                    row = current_data[(current_data['Линия'] =='q1-kz') & (current_data['Узел'] == q1_name)]
                    #test_print = True
                    #if test_print: print(f'анализ защиты {line}|{node} возле if')
                elif line == line_kz and node == q2_name and q2_off== False:
                    row = current_data[(current_data['Линия'] == 'kz-q2') & (current_data['Узел'] == q2_name)]
                    #test_print = True
                    #print('!!! Начат анализ защиты', line, '|', node)
                else:
                    row = current_data[(current_data['Линия'] == line) & (current_data['Узел'] == node)]
                    #print(row['I0'])
                #print('!!! Начат анализ защиты 3', line, '|', node)
                if row.empty:
                    continue
                
                # Извлекаем значения тока и мощности
                I0 = row['I0'].values[0]
                I0 = complex(I0)
                S0 = row['S0'].values[0]
                S0 = complex(I0)
                
                protection_key = f"{line}|{node}-{prot['№ ступени']}"
                if test_print: print(f'анализ защиты {line}|{node}')
                # Проверяем условие срабатывания РНМ, если оно введено
                rnm_check_passed = True
                if prot['Введена ли РНМ']:
                    rnm_check_passed = check_rnm_I_df(row, prot)#check_rnm(S0, prot['мощность сраб РНМ'], prot['угол РНМ'])
                    
                if rnm_check_passed:
                    #if test_print: print(f'РНМ сработал, пошел анализ {protection_key} токи уст {Kch_I0} факт {abs(I0)}')
                    # Вычисляем уставки по току с учетом коэффициентов чувствительности и отстройки
                    Kch_I0 = prot['I0_сраб']/prot['Kч']
                    Kots_I0 = prot['I0_сраб']/prot['Котс']
                    
                    # Проверяем условия срабатывания защиты
                    if (line == line_kz and abs(I0) >= Kch_I0):
                        #if test_print: print(f'выполнены условия срабатывания защиты {protection_key} ток {abs(I0)}  уставка с кч {Kch_I0}')
                        #prot['Почувствовала']=True
                        all_protections.loc[i,'Почувствовала'] = True
                        #print(protection_key)
                    
                    if (line != line_kz and abs(I0) >= Kots_I0):
                        #if test_print: 
                        #print(f'выполнены условия срабатывания защиты {protection_key} ток {abs(I0)} уставка с кots {Kots_I0}')
                        #prot['Почувствовала']=True
                        all_protections.loc[i,'Почувствовала'] = True
                        #print(protection_key)

                    
                    elif abs(I0) <= prot['I0_сраб']*prot['Кв']:
                        #if test_print: print(f'реле отпало по току c {protection_key} токи уст {Kch_I0} факт {abs(I0)}')
                        #prot['Времени до срабатывания'] = prot['t_сраб']
                        all_protections.loc[i,'Времени до срабатывания']= prot['t_сраб']
                    # Здесь нужно добавить логику для обработки protection_start_times
                    # if protection_key not in protection_start_times:
                    #     protection_start_times[protection_key] = total_time
                else:
                    prot['Времени до срабатывания'] = prot['t_сраб']
                    #prot['Времени до срабатывания'] = prot['t_сраб']
                    all_protections.loc[i,'Времени до срабатывания']= prot['t_сраб']
            # Сортируем защиты по времени срабатывания
            all_protections = all_protections.sort_values(by='Времени до срабатывания')
            # Находим время срабатывания ближайшей защиты первого пояса
            #a = all_protections.loc[all_protections['Почувствовала']].count()[0]
                

            try:
                total_time = all_protections.loc[(all_protections['Линия'] == line_kz) & (all_protections['Почувствовала'])].head(1)['Времени до срабатывания'].values[0]
                x = all_protections.loc[(all_protections['Линия'] == line_kz) & (all_protections['Почувствовала'])].count()[0]    

            except:
                try: belt = row['Пояс'].values[0]
                except: belt = 4
                new_result = pd.DataFrame({
                        'Линия КЗ': [line_kz],
                        'Тип КЗ': [kz_type],
                        'Место КЗ': [kz_percent],
                        'Сработавшая защита': [f"Защиты не чувствуют"],
                        'Ступень защиты': [0],
                        'Ток срабатывания': [0],
                        'Ток КЗ': [0],
                        'Время срабатывания': [total_time],
                        'Отключенные линии': [off_lines],
                        'Группа отключения': [j],
                        'Пояс': [belt] })
                if print_log: print(f"КЗ не отключено:{off_lines} ")
                results = pd.concat([results, new_result], ignore_index=True)
                off = True      

            if off == True:
                break
            # Отмечаем сработавшие защиты
            distant_belts_off_lines += all_protections.loc[(all_protections['Времени до срабатывания'] <= total_time) & (all_protections['Почувствовала']) & (all_protections['Линия'] != line_kz),'Линия'].unique().tolist()
            # Выделяем сработавшие защиты в отдельный DataFrame
            worked_protections = all_protections.loc[(all_protections['Времени до срабатывания'] <= total_time) & (all_protections['Почувствовала'])]
            # Уменьшаем время до срабатывания для оставшихся активных защит
            all_protections.loc[(all_protections['Времени до срабатывания'] > total_time) & (all_protections['Почувствовала']), 'Времени до срабатывания'] -= total_time
            
            
            
            
            # Записываем результаты сработавших защит
            for _, protection in worked_protections.iterrows():
                line = protection['Линия']
                node = protection['узел']
                # Находим соответствующую строку данных для текущей защиты
                if line == line_kz and node == q1_name and q1_off==False:
                    row = current_data[(current_data['Линия'] == 'q1-kz') & (current_data['Узел'] == q1_name)]
                    #print('q1_I0')
                    q1_off =True
                    #I0 = complex(row['I0'].values[0])
                    #print(f'выполнены условия срабатывания защиты {line} ток {abs(I0)}  уставка с кч {Kch_I0}')
                    current_data = kz_group.loc[kz_group['Каскад']==1]
                    if print_log: print(f"Отключена линия КЗ {line_kz} со стороны {node}, время: {total_time}")
                elif line == line_kz and node == q2_name and q2_off== False:
                    row = current_data[(current_data['Линия'] =='kz-q2') & (current_data['Узел'] == q2_name)]
                    q2_off =True
                    current_data = kz_group.loc[kz_group['Каскад']==2]
                    if print_log: print(f"Отключена линия КЗ {line_kz} со стороны {node}, время: {total_time}")
                else:
                    row = current_data[(current_data['Линия'] == line) & (current_data['Узел'] == node)]
                
                #print(row['I0'])
                try: I0 = complex(row['I0'].values[0])
                except: I0 = 0
                trip_time = past_total_time + protection['Времени до срабатывания']
                try: belt = row['Пояс'].values[0]
                except: belt = 4
                new_result = pd.DataFrame({
                            'Линия КЗ': [line_kz],
                            'Тип КЗ': [kz_type],
                            'Место КЗ': [kz_percent],
                            'Сработавшая защита': [f"{line} | {node}"],
                            'Ступень защиты': [protection['№ ступени']],
                            'Ток срабатывания': [protection['I0_сраб']],
                            'Ток КЗ': [abs(I0)],
                            'Время срабатывания': [trip_time],
                            'Отключенные линии': [off_lines],
                            'Группа отключения': [j],
                            'Пояс': [belt] })
                results = pd.concat([results, new_result], ignore_index=True)
            '''       
            # Проверяем условия завершения анализа
            kz_line_data = current_data[current_data['Линия'].isin(["kz-q2", "q1-kz"])]
            #print(kz_line_data)
            if (q1_off and q2_off) or (q1_off and q2_name=='0') or (q2_off and q1_name=='0'):
                if print_log: print("Линия кз отключена")
                if print_log: print(f"Всего строк в результате: {len(results)}")                   
                break      
            '''
            #print(kz_line_data)
            # Проверяем условия завершения анализа
            kz_line_data = current_data[current_data['Линия'].isin(["kz-q2", "q1-kz"])]
            kz_line_data['I0'] = kz_line_data['I0'].apply(lambda x: complex(x) if isinstance(x, str) else x)    
            
            if (q1_off and q2_off) or (q1_off and q2_name=='0') or (q2_off and q1_name=='0'):
                if print_log: print("Линия кз отключена")
                if print_log: print(f"Всего строк в результате: {len(results)}")                   
                break    
                

            elif (all(abs(kz_line_data['I0']) < 1e-6)): #and all(abs(kz_line_data['S0']) < 1e-6)):
                if print_log: print("Ток и напряжение в обоих узлах линии КЗ стали нулевыми")
                if print_log: print(f"Всего строк в результате: {len(results)}")               
                break
    
    
    return results











#                                Группа функций для рисования границы срабатывания защиты



# ФУНКЦИЯ НАХОДИТ ГРАНИЦЫ СТРАБАТЫВАНИЯ ЗАЩИТЫ В УЗЛЕ Q ЛИНИИ LINE ПРИ КЗ В УЗЛЕ P
def find_tehe_def_edge(mdl, line, q, p, step, prot_stage, log=False):
    
    line_obj = p_search(mdl, p_name=line)
    #print(line_obj)
    if line_obj.q1 == 0:
        is_q1 = False
        # Нходим уставку ступени
        for prot in line_obj.q2_def:
            if prot.stage == prot_stage:
                I_def = prot.I0
            
    elif line_obj.q1.name == q: 
        is_q1 = True
        # Нходим уставку ступени
        for prot in line_obj.q2_def:
            if prot.stage == prot_stage:
                I_def = prot.I0
                
    else:
        is_q1 = False
        # Нходим уставку ступени
        for prot in line_obj.q2_def:
            if prot.stage == prot_stage:
                I_def = prot.I0
                    
    try:  p_q1_name = p.q1.name   
    except: p_q1_name = '0'
    try:  p_q2_name = p.q2.name   
    except: p_q2_name = '0'
    if is_q1: q_other = line_obj.q2.name
    else:     q_other = line_obj.q1.name    
    if line==p.name:
        p_is_q1 = is_q1
    elif p_q1_name == q_other:
        p_is_q1 = True
    elif p_q2_name == q_other:
        p_is_q1 = False
    #elif (p.q1 == line_obj.q2 and is_q1) or (p.q1 == line_obj.q1 and is_q1==False):
            #p_is_q1 = True
    #elif (p.q2 == line_obj.q2 and is_q1) or (p.q2 == line_obj.q1 and is_q1==False):
            #p_is_q1 = False
    else:
        #print(p.name)
        return {}
    i = 0
    while i <= 1:
        if log: print(p_is_q1)
        i+=step
        if p_is_q1: j=i
        else:     j=1-i       
        sub_mdl = kz_q(mdl, line=p, percentage_of_line=j, show_G=False)
        mrtkz.N(sub_mdl,'KZ',sub_mdl.bq[-1],'A0')
        sub_mdl.Calc()
        
        if line==p.name: 
            if is_q1: line_obj = p_search(sub_mdl, p_name='q1-kz')
            else:     line_obj = p_search(sub_mdl, p_name='kz-q2')
        else: line_obj = p_search(sub_mdl, p_name=line)
        
        
        if is_q1: 
            I0 = abs(complex(line_obj.res1(parnames=['I0'])['I0']))
                    
        else:      
            I0 = abs(complex(line_obj.res2(parnames=['I0'])['I0']))
    
        #if log: print(f'Если {I_def} > {I0}, {j*100}%')
        if I_def>I0:
            if log: print('результат')
            res ={'линия кз':p.name,'место кз':i,'номер ступени':prot_stage}
            return res
    res ={'линия кз':p.name,'место кз':i,'номер ступени':prot_stage}  
    return res
    
# ФУНКЦИЯ НАХОДИТ ГРАНИЦЫ СТРАБАТЫВАНИЯ ЗАЩИТЫ ДЛЯ ВСЕГО ПЕРВОГО ПОЯСА
def protection_edge_dict(prot, i_step=0.05):
    q = prot.q
    line_obj = prot.p
    mdl = prot.p.model
    stage = prot.stage
    if line_obj.q1 == 0 or line_obj.q2 == 0:
        raise ValueError('Линия 1 тупиковая')
    if line_obj.q1 == q: q_other = line_obj.q2
    else:                q_other = line_obj.q1
    
    # пройдемся по собственной линии
    result = find_tehe_def_edge(mdl=mdl, line=line_obj.name, q=q.name, p=line_obj, step=i_step, prot_stage=stage)
    if result['место кз']< 1:
        return result
    else:
        result = {'линия кз':'','место кз':'','номер ступени':''}
        for p in q_other.plist:
            if p.name != line_obj.name:
                new_result = find_tehe_def_edge(mdl=mdl, line=line_obj.name, q=q.name, p=p, step=i_step, prot_stage=stage)
                #print(new_result)
                #result = {key: [result.get(key), new_result.get(key)] for key in result.keys() | new_result.keys()}
                #for key in new_result.keys():
                # Проверяем, существует ли уже значение для данного ключа в result
                for key in result.keys():
                    # Проверяем, существует ли уже значение для данного ключа в result
                    if key in result:
                        # Если текущее значение в result не является списком, превращаем его в список
                        if not isinstance(result[key], list):
                            result[key] = [result[key]]
                        # Добавляем новое значение в список
                        result[key].append(new_result[key])
                    else:
                        # Если ключа нет в result, просто добавляем его
                        result[key] = new_result[key]
                    
        return result
#protection_edge_dict(prot)

# ФУНКЦИЯ РИСОВАНИЯ ЭНЕРГОСИСТЕМЫ

def draw_power_grid_with_faults(line, first_belt_list, kz_dict, bus_list):

    
    # Redrawing the figure with the correct specifications
    fig, ax = plt.subplots()
    
    # Circle for the generator with an AC symbol inside (~), centered and larger
    circle = plt.Circle((1, 7), 1, fill=False, color='blue')
    ax.add_patch(circle)
    plt.text(1, 7, '~', fontsize=20, verticalalignment='center', horizontalalignment='center')  # AC symbol

    # Adjusted label for the generator
    plt.text(0.2, 9, 'Sys', fontsize=10, verticalalignment='center')

    # Draw thick vertical line (PS1 equivalent) with an adjustable length based on the number of lines
    belt_center_x, belt_center_y = 10, 7
    num_lines = len(first_belt_list)
    belt_half_length = 1 + (num_lines * 1.5)  # Adjust length based on number of lines
    plt.plot([belt_center_x, belt_center_x], [belt_center_y - belt_half_length, belt_center_y + belt_half_length], 'k-', lw=6)
    plt.text(belt_center_x, belt_center_y + belt_half_length + 0.5, bus_list[1], fontsize=10, verticalalignment='center', horizontalalignment='center')

    # New line from Gen1 to Sys1 with a substation (length 2) and a vertical PS1 line
    sys1_x_end = 3  # x-coordinate for Sys1 (end of the new line from Gen1)
    plt.plot([2, sys1_x_end], [7, 7], 'g-')  # Line Gen1-Sys1
    #plt.text(1.5, 7.2, 'Gen1-Sys1', fontsize=10, color='green')

    # Vertical line for Sys1 substation
    plt.plot([sys1_x_end, sys1_x_end], [6, 8], 'k-', lw=6)  # Sys1 substation
    plt.text(sys1_x_end, 8.5, bus_list[0], fontsize=10, verticalalignment='center', horizontalalignment='center')

    # Draw the first line (Sys1-PS1) from Sys1 to the center belt (PS1)
    plt.plot([sys1_x_end, belt_center_x], [7, belt_center_y], 'g-')
    plt.text((sys1_x_end + belt_center_x) / 2, 7.7, line, fontsize=10, color='green')

    # Drawing parallel lines from PS1 to subsequent belts (PS2, PS3, etc.)
    belt_line_x_start = belt_center_x
    belt_line_x_end = 20
    y_spacing = num_lines*3 / (num_lines - 1) if num_lines > 1 else 0  # Even spacing between lines, centered on y=7
    y_start = belt_center_y + (num_lines - 1) * y_spacing / 2
    j=1
    for i, line_name in enumerate(first_belt_list):
        j+=1 
        y_pos = y_start - i * y_spacing
        plt.plot([belt_line_x_start, belt_line_x_end], [y_pos, y_pos], 'r-', lw=2)
        plt.text((belt_line_x_start + belt_line_x_end) / 2, y_pos + 0.7, line_name, fontsize=10, color='red')
        
        # Add vertical belt at the end of each line
        plt.plot([belt_line_x_end, belt_line_x_end], [y_pos - 1, y_pos + 1], 'k-', lw=6)
        plt.text(belt_line_x_end, y_pos + 1.5, bus_list[j], fontsize=10, verticalalignment='center', horizontalalignment='center')

    # Drawing fault points based on kz_dict
    for fault_line, fault_percent, fault_step in zip(kz_dict['линия кз'], kz_dict['место кз'], kz_dict['номер ступени']):
        if fault_line in first_belt_list:
            line_idx = first_belt_list.index(fault_line)
            y_pos = y_start - line_idx * y_spacing
            x_fault = belt_line_x_start + fault_percent * (belt_line_x_end - belt_line_x_start)
            plt.plot(x_fault, y_pos, 'ro')  # red point for fault
            plt.text(x_fault + 0.2, y_pos + 0.3, f'ст {fault_step}', fontsize=10, color='red')
        elif fault_line == line:
            y_pos = 7
            x_fault = sys1_x_end + fault_percent * (belt_center_x - sys1_x_end)
            plt.plot(x_fault, y_pos, 'ro')  # red point for fault
            plt.text(x_fault + 0.2, y_pos + 0.3, f'ст {fault_step}', fontsize=10, color='red')            

    
    # Set the limits of the plot
    ax.set_xlim(0, 23)
    ax.set_ylim(0, 15)

    # Equal scaling and grid for better visualization
    ax.set_aspect('equal')
    ax.grid(False)

    # Show the plot
    plt.show()

# Test the function with input values and a fault dictionary
#line = 'Sys1-PS1'
#first_belt_list = ['PS1-PS2', 'PS1-PS3', 'PS1-PS4']
#kz_dict = {'линия кз': ['PS1-PS2', 'PS1-PS3'], 'место кз': [0.3, 0.7], 'номер ступени': [2, 3]}
#bus_list = ['Sys1','PS1','PS2','PS3','PS4']
#draw_power_grid_with_faults(line, first_belt_list, kz_dict, bus_list)




# ИТОГОВАЯ ФУНКЦИЯ, ВИЗУАЛИЗИРУЕТ ГРАНИЦУ СРАБАТЫВАНИЯ ВСЕХ ЗАЩИТ ВЫКЛЮЧАТЕЛЯ

def protection_visual(mdl,p,is_q1=True):
    if is_q1:
        q = p.q1
        q_other = p.q2
    else:
        q = p.q2
        q_other = p.q1
    
    #if p.q1==q: q_other = p.q2
    #elif p.q2==q: q_other = p.q1    
    #if not q in [p.q1,p.q2]:
    #    raise ValueError('Узел не часть линии')
    if p.q1==0:
        raise ValueError('Узел q1 - нулевой')  
    if p.q2==0:
        raise ValueError('Узел q2 - нулевой')        
        
    bus_list = []
    if q == p.q1:
        # добавим первую подстанцию
        bus_list.append(p.q1.name) # добавим первую подстанцию
        bus_list.append(p.q2.name) # добавим вторую подстанцию
    elif q == p.q2:
        bus_list.append(p.q2.name) # добавим первую подстанцию
        bus_list.append(p.q1.name) # добавим вторую подстанцию
    kz_dict = {'линия кз': '', 'место кз': '', 'номер ступени': ''}
    if q==p.q1:
        for prot in p.q1_def:
        
            new_kz_dict = protection_edge_dict(prot)
            
            for key in kz_dict.keys():
                # Проверяем, существует ли уже значение для данного ключа в kz_dict
                if key in kz_dict:
                    # Если текущее значение не список, превращаем его в список
                    if not isinstance(kz_dict[key], list):
                        kz_dict[key] = [kz_dict[key]]
                        
                    # Если новое значение - список, добавляем его элементы
                    if isinstance(new_kz_dict[key], list):
                        kz_dict[key].extend(new_kz_dict[key])
                    else:
                        kz_dict[key].append(new_kz_dict[key])
                else:
                    # Если ключа нет в kz_dict, просто добавляем его
                    kz_dict[key] = new_kz_dict[key]
    if q==p.q2:
        for prot in p.q2_def:
        
            new_kz_dict = protection_edge_dict(prot)
            
            for key in kz_dict.keys():
                # Проверяем, существует ли уже значение для данного ключа в kz_dict
                if key in kz_dict:
                    # Если текущее значение не список, превращаем его в список
                    if not isinstance(kz_dict[key], list):
                        kz_dict[key] = [kz_dict[key]]
                        
                    # Если новое значение - список, добавляем его элементы
                    if isinstance(new_kz_dict[key], list):
                        kz_dict[key].extend(new_kz_dict[key])
                    else:
                        kz_dict[key].append(new_kz_dict[key])
                else:
                    # Если ключа нет в kz_dict, просто добавляем его
                    kz_dict[key] = new_kz_dict[key]    
                    
    line = prot.p.name
    first_belt_list = []
    
    
    for p in q_other.plist:
        if p.name != line:
            first_belt_list.append(p.name)
            if p.q1==0 or p.q2==0:
                bus_list.append('0')
            elif p.q1.name == bus_list[1]:
                    bus_list.append(p.q2.name) # добавим линии первого пояса

            elif p.q2.name == bus_list[1]:
                    bus_list.append(p.q1.name) # добавим линии первого пояса

    #print(first_belt_list)
    draw_power_grid_with_faults(line, first_belt_list, kz_dict, bus_list)
    #print(bus_list)
    #print()
    #print(first_belt_list)
    #print()
    #print(kz_dict)


#protection_visual(mdl=mdl,p=mdl.bp[2],is_q1=False)

# kz_3f_ots_to_result_df(mdl,base_df, def_df)



#Поиск пояса линии 0-4

def belts_full_list(line, is_name=True):
    belt_dict = {}
    first_belt_lines = []
    # Первый пояс: линии, непосредственно подключенные к заданной
    try:
        line.q1
        first_belt_lines = [p for p in line.q1.plist if p.name != line.name]
    except:
        1
    
    try:
        line.q2
        first_belt_lines.extend([p for p in line.q2.plist if p.name != line.name])
    except:    
        1
    first_belt_lines = list(set(first_belt_lines))  # Удаляем дубликаты
    
    # Добавляем первый пояс в словарь
    for p in first_belt_lines:
        if is_name: belt_dict[p.name] = 1
        else: belt_dict[p.id] = 1

    # Второй пояс: линии, подключенные к линиям первого пояса
    second_belt_lines = []
    for first_belt_line in first_belt_lines:
        if first_belt_line.q1 != 0:
            second_belt_lines.extend([p for p in first_belt_line.q1.plist if p.name != first_belt_line.name and p.name != line.name])
        if first_belt_line.q2 != 0:
            second_belt_lines.extend([p for p in first_belt_line.q2.plist if p.name != first_belt_line.name and p.name != line.name])
    
    second_belt_lines = list(set(second_belt_lines))  # Удаляем дубликаты

    # Добавляем второй пояс в словарь
    for p in second_belt_lines:
        if p.id not in belt_dict:  # Если линия уже не находится в первом поясе
            if is_name: belt_dict[p.name] = 2
            else: belt_dict[p.id] = 2

    # Третий пояс: линии, подключенные к линиям второго пояса
    third_belt_lines = []
    for second_belt_line in second_belt_lines:
        if second_belt_line.q1 != 0:
            third_belt_lines.extend([p for p in second_belt_line.q1.plist if p.name != second_belt_line.name and p.name not in {line.name} | {l.name for l in first_belt_lines}])
        if second_belt_line.q2 != 0:
            third_belt_lines.extend([p for p in second_belt_line.q2.plist if p.name != second_belt_line.name and p.name not in {line.name} | {l.name for l in first_belt_lines}])
    
    third_belt_lines = list(set(third_belt_lines))  # Удаляем дубликаты

    # Добавляем третий пояс в словарь
    for p in third_belt_lines:
        if p.id not in belt_dict:  # Если линия уже не находится в первом или втором поясах
            if is_name: belt_dict[p.name] = 3
            else: belt_dict[p.id] = 3
                

    return belt_dict


def mdl_belts_full_dict(mdl, is_name=True):
    mdl_belts_full_list = {}
    for p in mdl.bp:
        if is_name:
            mdl_belts_full_list[p.name] = belts_full_list(p) 
        else:
            mdl_belts_full_list[p.id] = belts_full_list(p)
    return mdl_belts_full_list


# Выводит визуализацию графа с токами и направлениями
def vis_I0_graph(mdl):
    mdl.Calc()
    G = mdl.G
    label_dict = {}
    for p in mdl.bp:
        if p.q1!=0: q1_name = p.q1.name
        else:       q1_name = p.name+'_0'
            
        if p.q2!=0: q2_name = p.q2.name
        else:       q2_name = p.name+'_0'
            
        I0 = p.res1(['I0'], 'M')['I0']
        ang = p.res1(['I0'], '<f')['I0']
        if ((-20 <= ang <= 160) or (340 <= ang <= 360)):
            way = '->'
        else:
            way= '<-'
        line_label = q1_name + way + q2_name + '\n' + 'I0=' + str(round(I0))
        #line_label += '\n'+str(p.Z[2])
        #print(line_label)
        for pg in mdl.G.edges:
            if (q1_name, q2_name) == pg or (q2_name, q1_name) == pg: 
                line_g = pg
        # Добавление лейбла к конкретному ребру
        label_dict[line_g] = line_label
    
    
    #print(label_dict)   
    nx.set_edge_attributes(G, label_dict, 'label')
    pos = nx.get_node_attributes(mdl.G, 'pos')
    
    nx.draw(mdl.G, pos, with_labels=True, node_color='lightblue', node_size=500, font_size=10, font_weight='bold')
    edge_labels = nx.get_edge_attributes(mdl.G, 'label')
    nx.draw_networkx_edge_labels(mdl.G, pos, edge_labels=edge_labels, font_size=8, bbox=dict(boxstyle="round",pad=0, edgecolor='none', alpha=0))
    
    plt.title("Участок энергосистемы")
    plt.axis('off')
    plt.show()



'''
import pandas as pd
import numpy as np
import cmath



def check_rnm_df(df_row):
    I0 = df_row['I0'].values[0]
    U0 = df_row['U0'].values[0]
    S0 = U0 * np.conj(I0)
    S0_angle = cmath.phase(S0) * 180 / np.pi
    angle_diff = abs((S0_angle - df_row['угол макс РНМ'] + 180) % 360 - 180)
    
    if angle_diff > 90:
        return False
    
    if abs(S0) <= df_row['мощность сраб РНМ'] / np.cos(np.radians(angle_diff)):
        return False
    return True
    
def analyze_I_protection(mdl, def_df, base_df, line_kz, print_log = False):
    # Создаем DataFrame для хранения результатов анализа
    results = pd.DataFrame(columns=['Линия КЗ', 'Тип КЗ', 'Место КЗ', 'Сработавшая защита', 
                                'Ступень защиты', 'Ток срабатывания', 'Ток КЗ', 'Время срабатывания', 'Отключенные линии', 'Группа отключения'])
    
    # Перебираем все уникальные комбинации типа КЗ, места КЗ и отключенных ветвей для заданной линии КЗ
    for (kz_type, kz_percent, kz_off_lines), kz_group in base_df[base_df['Линия кз'] == line_kz].groupby(['Тип кз', 'Место кз', 'Отключенные ветви']):
        j=0
        past_total_time = 0
        total_time = 0
        tripped_lines = set()
        current_data = kz_group.loc[kz_group['Каскад']==0]
        try: q1_name = p_search(mdl=mdl,p_name=line_kz).q1.name
        except: q1_name = '0'
        try: q2_name = p_search(mdl=mdl,p_name=line_kz).q2.name
        except: q2_name = '0'             
        q1_off = False
        q2_off = False
        
        # Определяем узлы линии КЗ и список линий первого пояса
        #kz_q12 = base_df.loc[(base_df['Линия']==line_kz)]['Узел'].unique()
        #kz_1_belt_lines_list = base_df.loc[base_df['Узел'].isin(kz_q12)]['Линия'].unique()
        #belt_lines_count = len(kz_1_belt_lines_list)


        kz_q12 = base_df.loc[(base_df['Линия']==line_kz)]['Узел'].unique()
        #kz_1_belt_lines_list = base_df.loc[base_df['Узел'].isin(kz_q12)]['Линия'].unique()
        elements_to_remove = ['q1-kz', 'kz-q2', line_kz]
        #kz_1_belt_lines_tuple = (tuple(item for item in kz_1_belt_lines_list if item not in elements_to_remove))
        
        
        if print_log: print(f"Анализ КЗ: Линия {line_kz}, Тип {kz_type}, Место {kz_percent}, Отключенные ветви {kz_off_lines}")
        
        # Выбираем все активные защиты, и сортируем их по времени срабатывания
        all_protections = def_df[(def_df['Введена ли защита'] == True)].sort_values('t_сраб')
        all_protections['Времени до срабатывания'] = all_protections['t_сраб']        
        all_protections['Сработала'] = False  
        all_protections.reset_index(drop=True, inplace=True)        
        off_lines = kz_off_lines
        distant_belts_off_lines = []
        while True:
            
            all_protections['Почувствовала'] = False   
            off = False
            if current_data.empty:
                if print_log: print("Нет данных для анализа")
                break
                
            past_total_time = total_time
            
            j+=1
            i=-1
            # Проверяем каждую защиту
            for _, prot in all_protections.iterrows():
                test_print=False
                temp_off_lines = ()
                i+=1
                line = prot['Линия']
                node = prot['узел']
                # Пропускаем уже отключенные линии
                if line in distant_belts_off_lines:
                    continue
                if line == line_kz and node == q1_name and q1_off==True:
                    continue
                if line == line_kz and node == q2_name and q2_off==True:
                    continue    
                # Находим соответствующую строку данных для текущей защиты
                if line == line_kz and node == q1_name and q1_off==False:
                    row = current_data[(current_data['Линия'] =='q1-kz') & (current_data['Узел'] == q1_name)]
                    #test_print = True
                    #if test_print: print(f'анализ защиты {line}|{node} возле if')
                elif line == line_kz and node == q2_name and q2_off== False:
                    row = current_data[(current_data['Линия'] == 'kz-q2') & (current_data['Узел'] == q2_name)]
                    #test_print = True
                    #print('!!! Начат анализ защиты', line, '|', node)
                else:
                    row = current_data[(current_data['Линия'] == line) & (current_data['Узел'] == node)]
                    #print(row['I0'])
                #print('!!! Начат анализ защиты 3', line, '|', node)
                if row.empty:
                    continue
                
                # Извлекаем значения тока и мощности
                I0 = row['I0'].values[0]
                I0 = complex(I0)
                S0 = row['S0'].values[0]
                S0 = complex(I0)
                
                protection_key = f"{line}|{node}-{prot['№ ступени']}"
                if test_print: print(f'анализ защиты {line}|{node}')
                # Проверяем условие срабатывания РНМ, если оно введено
                rnm_check_passed = True
                if prot['Введена ли РНМ']:
                    rnm_check_passed = check_rnm(S0, prot['мощность сраб РНМ'], prot['угол РНМ'])
                    
                if rnm_check_passed:
                    #if test_print: print(f'РНМ сработал, пошел анализ {protection_key} токи уст {Kch_I0} факт {abs(I0)}')
                    # Вычисляем уставки по току с учетом коэффициентов чувствительности и отстройки
                    Kch_I0 = prot['I0_сраб']/prot['Kч']
                    Kots_I0 = prot['I0_сраб']/prot['Котс']
                    
                    # Проверяем условия срабатывания защиты
                    if (line == line_kz and abs(I0) >= Kch_I0):
                        #if test_print: print(f'выполнены условия срабатывания защиты {protection_key} ток {abs(I0)}  уставка с кч {Kch_I0}')
                        #prot['Почувствовала']=True
                        all_protections.loc[i,'Почувствовала'] = True
                        #print(protection_key)
                    
                    if (line != line_kz and abs(I0) >= Kots_I0):
                        #if test_print: 
                        #print(f'выполнены условия срабатывания защиты {protection_key} ток {abs(I0)} уставка с кots {Kots_I0}')
                        #prot['Почувствовала']=True
                        all_protections.loc[i,'Почувствовала'] = True
                        #print(protection_key)

                    
                    elif abs(I0) <= prot['I0_сраб']*prot['Кв']:
                        #if test_print: print(f'реле отпало по току c {protection_key} токи уст {Kch_I0} факт {abs(I0)}')
                        #prot['Времени до срабатывания'] = prot['t_сраб']
                        all_protections.loc[i,'Времени до срабатывания']= prot['t_сраб']
                    # Здесь нужно добавить логику для обработки protection_start_times
                    # if protection_key not in protection_start_times:
                    #     protection_start_times[protection_key] = total_time
                else:
                    prot['Времени до срабатывания'] = prot['t_сраб']
                    #prot['Времени до срабатывания'] = prot['t_сраб']
                    all_protections.loc[i,'Времени до срабатывания']= prot['t_сраб']
            # Сортируем защиты по времени срабатывания
            all_protections = all_protections.sort_values(by='Времени до срабатывания')
            # Находим время срабатывания ближайшей защиты первого пояса
            #a = all_protections.loc[all_protections['Почувствовала']].count()[0]
                

            try:
                total_time = all_protections.loc[(all_protections['Линия'] == line_kz) & (all_protections['Почувствовала'])].head(1)['Времени до срабатывания'].values[0]
                x = all_protections.loc[(all_protections['Линия'] == line_kz) & (all_protections['Почувствовала'])].count()[0]    

            except:
                new_result = pd.DataFrame({
                        'Линия КЗ': [line_kz],
                        'Тип КЗ': [kz_type],
                        'Место КЗ': [kz_percent],
                        'Сработавшая защита': [f"Защиты не чувствуют"],
                        'Ступень защиты': [0],
                        'Ток срабатывания': [0],
                        'Ток КЗ': [0],
                        'Время срабатывания': [total_time],
                        'Отключенные линии': [off_lines],
                        'Группа отключения': [j]
                    })
                if print_log: print(f"КЗ не отключено:{off_lines} ")
                results = pd.concat([results, new_result], ignore_index=True)
                off = True      

            if off == True:
                break
            # Отмечаем сработавшие защиты
            distant_belts_off_lines += all_protections.loc[(all_protections['Времени до срабатывания'] <= total_time) & (all_protections['Почувствовала']) & (all_protections['Линия'] != line_kz),'Линия'].unique().tolist()
            # Выделяем сработавшие защиты в отдельный DataFrame
            worked_protections = all_protections.loc[(all_protections['Времени до срабатывания'] <= total_time) & (all_protections['Почувствовала'])]
            # Уменьшаем время до срабатывания для оставшихся активных защит
            all_protections.loc[(all_protections['Времени до срабатывания'] > total_time) & (all_protections['Почувствовала']), 'Времени до срабатывания'] -= total_time
            
            
            
            
            # Записываем результаты сработавших защит
            for _, protection in worked_protections.iterrows():
                line = protection['Линия']
                node = protection['узел']
                # Находим соответствующую строку данных для текущей защиты
                if line == line_kz and node == q1_name and q1_off==False:
                    row = current_data[(current_data['Линия'] == 'q1-kz') & (current_data['Узел'] == q1_name)]
                    #print('q1_I0')
                    q1_off =True
                    #I0 = complex(row['I0'].values[0])
                    #print(f'выполнены условия срабатывания защиты {line} ток {abs(I0)}  уставка с кч {Kch_I0}')
                    current_data = kz_group.loc[kz_group['Каскад']==1]
                    if print_log: print(f"Отключена линия КЗ {line_kz} со стороны {node}, время: {total_time}")
                elif line == line_kz and node == q2_name and q2_off== False:
                    row = current_data[(current_data['Линия'] =='kz-q2') & (current_data['Узел'] == q2_name)]
                    q2_off =True
                    current_data = kz_group.loc[kz_group['Каскад']==2]
                    if print_log: print(f"Отключена линия КЗ {line_kz} со стороны {node}, время: {total_time}")
                else:
                    row = current_data[(current_data['Линия'] == line) & (current_data['Узел'] == node)]
                
                #print(row['I0'])
                try: I0 = complex(row['I0'].values[0])
                except: I0 = 0
                trip_time = past_total_time + protection['Времени до срабатывания']

                new_result = pd.DataFrame({
                            'Линия КЗ': [line_kz],
                            'Тип КЗ': [kz_type],
                            'Место КЗ': [kz_percent],
                            'Сработавшая защита': [f"{line} | {node}"],
                            'Ступень защиты': [protection['№ ступени']],
                            'Ток срабатывания': [protection['I0_сраб']],
                            'Ток КЗ': [abs(I0)],
                            'Время срабатывания': [trip_time],
                            'Отключенные линии': [off_lines],
                            'Группа отключения': [j] })
                results = pd.concat([results, new_result], ignore_index=True)
                    
            # Проверяем условия завершения анализа
            kz_line_data = current_data[current_data['Линия'].isin(["kz-q2", "q1-kz"])]
            #print(kz_line_data)
            if (q1_off and q2_off) or (q1_off and q2_name=='0') or (q2_off and q1_name=='0'):
                if print_log: print("Линия кз отключена")
                if print_log: print(f"Всего строк в результате: {len(results)}")                   
                break      
                
            
    return results
'''
'''
# Пример использования функции
base_df.reset_index(drop=True, inplace=True) 
def_df.reset_index(drop=True, inplace=True) 
#result_df = analyze_I_protection(mdl, def_df, base_df, 'PS1-PS2')
#print(result_df)
'''