"""
Расширения библиотеки mrtkz3 для моделирования релейной защиты энергосистем.

Функции:
  base_model              -- тестовая модель (5 узлов, 6 линий, 4 ступени защит)
  kz_q / q_del / p_del   -- формирование подрежимов (добавление узла КЗ, удаление ветвей/узлов)
  duplicate_mdl           -- копирование модели
  p_search / q_search     -- поиск ветвей и узлов по имени
  belt_search             -- обход топологии по поясам защиты
  generate_line_combinations / line_enumiration -- перебор вариантов отключений
  print_G                 -- визуализация схемы сети
  find_tehe_def_edge / protection_edge_dict / protection_visual -- анализ и визуализация срабатываний
  mdl_belts_full_dict / belts_full_list -- словари поясной структуры сети
"""
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import spsolve
import mrtkz3 as mrtkz
from collections import deque
import itertools


def base_model():
    """
    Создаёт и возвращает тестовую модель энергосистемы.

    Топология: 5 узлов (PS1–PS5), 6 воздушных линий, 2 источника ЭДС,
    3 трансформатора с заземлёнными нейтралями, взаимоиндукция L4-L5.
    На каждую ветвь добавлены 4 ступени ТЗНП с уставками I0=3000/2000/1000/0 А
    и t=0/1/2/3 с. Одна дополнительная ступень 9 на Line5.

    Возвращает:
        mdl -- объект модели mrtkz.Model (не рассчитана; прошла Test4Singularity)
    """
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




def kz_q(mdl, line, percentage_of_line=0.5, show_G=True, show_par=False, kaskade=False):
    """
    Добавляет промежуточный узел КЗ на линию и возвращает подмодель.

    Разбивает линию `line` в точке `percentage_of_line` на два участка (q1-kz и kz-q2),
    переносит защиты и взаимоиндукции, удаляет исходную ветвь через p_del.
    Если kaskade=True, дополнительно возвращает две подмодели с отключёнными участками вокруг КЗ.

    Параметры:
        mdl                -- базовая модель сети
        line               -- объект линии (mrtkz.P) для постановки КЗ
        percentage_of_line -- доля линии от узла q1 (0..1, по умолчанию: 0.5)
        show_G             -- вывод графа после создания подмодели (по умолчанию: True)
        show_par           -- вывод координат узла КЗ (по умолчанию: False)
        kaskade            -- режим каскада: возвращает 3 подмодели (по умолчанию: False)

    Возвращает:
        sub_mdl              -- подмодель с узлом KZ (kaskade=False)
        или (sub_mdl, sub_mdl_q1, sub_mdl_q2) при kaskade=True
    """
    if line.q1 == 0:
        q_x = line.q2.x + 0.25*percentage_of_line
        q_y = line.q2.y - 0.5*percentage_of_line
        
    elif line.q2 == 0:
        q_x = line.q1.x + 0.5*percentage_of_line
        q_y = line.q1.y + 1*percentage_of_line        
    else:
        q_x = line.q1.x + (line.q2.x - line.q1.x)*percentage_of_line
        q_y = line.q1.y + (line.q2.y - line.q1.y)*percentage_of_line

    sub_mdl = duplicate_mdl(mdl, show_G = False)
    
    KZ_q = mrtkz.Q(sub_mdl,'KZ', x=q_x, y=q_y) # создаем узел КЗ
    if show_par: print("X: ",KZ_q.x,"Y: ", KZ_q.y)
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


def q_del(mdl, del_q_name, show_G=True):
    """
    Создаёт подрежим с удалённым узлом и всеми связанными ветвями.

    Параметры:
        mdl         -- базовая модель сети
        del_q_name  -- имя удаляемого узла
        show_G      -- вывод графа после удаления (по умолчанию: True)

    Возвращает:
        submdl -- рассчитанная подмодель без узла del_q_name
    """
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

def p_del(mdl, del_p_name=[],q1_name='', q2_name='', show_G=True, show_par=False, node = False):
    """
    Создаёт подрежим с удалёнными ветвями (моделирование отключения линий).

    Ветвь задаётся именем (del_p_name) или парой узлов (q1_name, q2_name).
    Если node задан и граф становится несвязным, сохраняет только ветви,
    достижимые из узла node (BFS по графу).

    Параметры:
        mdl         -- базовая модель сети
        del_p_name  -- имя ветви (str), список имён (list) или кортеж (tuple) для удаления
        q1_name     -- имя первого узла удаляемой ветви (альтернатива del_p_name)
        q2_name     -- имя второго узла удаляемой ветви (альтернатива del_p_name)
        show_G      -- вывод графа после удаления (по умолчанию: True)
        show_par    -- вывод имён удалённых ветвей (по умолчанию: False)
        node        -- имя узла, от которого сохраняется связная компонента (по умолчанию: False)

    Возвращает:
        submdl -- подмодель без удалённых ветвей (не рассчитана)
    """
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
    """
    Находит ветвь в модели по имени или по именам двух узлов.

    Параметры:
        mdl    -- объект модели сети
        q1     -- имя первого узла (поиск по паре узлов)
        q2     -- имя второго узла (поиск по паре узлов)
        p_name -- имя ветви (поиск по имени)
        info   -- вывод предупреждения, если ветвь не найдена (по умолчанию: True)

    Возвращает:
        объект ветви mrtkz.P или '' если не найдена
    """
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
    """
    Находит узел в модели по имени.

    Параметры:
        mdl    -- объект модели сети
        q_name -- имя узла для поиска
        info   -- вывод предупреждения при отсутствии (по умолчанию: True)

    Возвращает:
        объект узла mrtkz.Q или '' если не найден
    """
    q_ser = ''
    for q in mdl.bq:
        if q.name==q_name: q_ser = q
    if q=='' and info: print('Введите название узла')
    #if  line=='': print('Линия не найдена')

    return q_ser




# функция создает новую модель и другие объекты на основании другой модели
def duplicate_mdl(mdl1, show_G = False):
    """
    Создаёт полную копию модели со всеми ветвями, узлами, защитами, взаимоиндукциями и несимметриями.

    Параметры:
        mdl1   -- исходная модель mrtkz.Model
        show_G -- вывод графа скопированной модели (по умолчанию: False)

    Возвращает:
        mdl2 -- новый объект mrtkz.Model, независимая копия mdl1
    """
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



# возвращает названия узлов линии, не ломаясь об нули
def line_q_names(line):
    try:    q1 = line.q1.name
    except: q1 = 0 
    try:    q2 = line.q1.name
    except: q2 = 0
    return [q1, q2]





def belt_search(mdl, line, n, return_names=False):
    """
    Обходит топологию сети по поясам от заданной линии (BFS по рёбрам).

    Пояс k — множество ветвей, достижимых ровно через k шагов от line.
    Ветвь line исключается из пояса 1.

    Параметры:
        mdl          -- объект модели сети
        line         -- исходная ветвь mrtkz.P
        n            -- максимальное число поясов
        return_names -- если True, возвращает имена вместо объектов (по умолчанию: False)

    Возвращает:
        (p_range_dict, q_range_dict) -- словари {пояс: set(ветвей/узлов)},
        ключ 'line' содержит имя исходной линии
    """
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



def generate_line_combinations(p_range_dict, m, show_info=True, return_as_list=False, belts_list = ''):
    """
    Генерирует все комбинации из m линий на основе словаря поясной структуры.

    Параметры:
        p_range_dict   -- словарь поясов из belt_search {пояс: set(линий)}
        m              -- количество одновременно отключаемых линий
        show_info      -- вывод числа линий и комбинаций (по умолчанию: True)
        return_as_list -- преобразовать список комбинаций явно в list (по умолчанию: False)
        belts_list     -- список номеров поясов для включения; '' = все пояса (по умолчанию: '')

    Возвращает:
        list -- список кортежей, каждый кортеж — набор из m линий
    """
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


def line_enumiration(mdl, line, max_belt_range, num_of_enum_lines, list_of_belts_for_enum='', return_names=False, show_info=True, return_as_list=True):
    """
    Комбинирует belt_search и generate_line_combinations для перебора вариантов отключений.

    Параметры:
        mdl                    -- объект модели сети
        line                   -- исходная ветвь (объект mrtkz.P) для отсчёта поясов
        max_belt_range         -- максимальный номер пояса для поиска
        num_of_enum_lines      -- количество одновременно отключаемых линий
        list_of_belts_for_enum -- список поясов для перебора; '' = все пояса (по умолчанию: '')
        return_names           -- возвращать имена вместо объектов (по умолчанию: False)
        show_info              -- вывод информации о числе комбинаций (по умолчанию: True)
        return_as_list         -- явно преобразовать в list (по умолчанию: True)

    Возвращает:
        list -- список кортежей вариантов отключений
    """
    p = belt_search(mdl=mdl, line=line, n=max_belt_range, return_names=return_names)[0]
    cmbinations = generate_line_combinations(p_range_dict=p, m=num_of_enum_lines, show_info=show_info, return_as_list=return_as_list, belts_list=list_of_belts_for_enum)
    return cmbinations


def generate_node_coordinates(mdl):
    # функция для генерации координат узлов
    mdl.Calc()
    G = mdl.G
    # Используем spring_layout для создания координат
    pos = nx.spring_layout(G)
    # Преобразуем позиции в нужный формат {узел: [x, y], ...}
    node_coordinates = {node: list(pos[node]) for node in G.nodes}

    for node, coords in node_coordinates.items():
        for q in mdl.bq:
            if q.name == node:
                q.edit_coords(3*coords[0], 3*coords[1])
    sub_mdl = duplicate_mdl(mdl)
    return sub_mdl


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



def p_del_elem(mdl, elem_name, show_G=False, show_par=False, node=False):
    """
    Создаёт подрежим с отключённым элементом (все ветви элемента удалены).

    Аналог p_del, но работает с объектом Element: находит элемент по имени
    и удаляет все его ветви одновременно.

    Параметры:
        mdl       -- базовая модель сети
        elem_name -- имя элемента (str или число, соответствующее Element.name)
        show_G    -- вывод графа после удаления (по умолчанию: False)
        show_par  -- вывод имён удалённых ветвей (по умолчанию: False)
        node      -- имя узла для сохранения связной компоненты (по умолчанию: False)

    Возвращает:
        submdl -- подмодель без ветвей элемента (не рассчитана)

    Исключения:
        ValueError -- если элемент с указанным именем не найден в модели
    """
    elem = next((e for e in mdl.be if str(e.name) == str(elem_name)), None)
    if elem is None:
        raise ValueError(f'Элемент {elem_name!r} не найден в модели')
    branch_names = tuple(p.name for p in elem.plist)
    return p_del(mdl, del_p_name=branch_names, show_G=show_G, show_par=show_par, node=node)


def kz_elem_q(mdl, elem_name, percent, show_G=False, show_par=False, kaskade=False):
    """
    Добавляет промежуточный узел КЗ на элемент на заданном проценте его длины.

    Определяет нужную ветвь элемента по соотношению |Z1| ветвей (суррогат длины).
    Для однородных элементов (одна ветвь) эквивалентен kz_q с той же долей.

    Параметры:
        mdl       -- базовая модель сети
        elem_name -- имя элемента (str или число)
        percent   -- позиция КЗ, доля от 0 до 1 (напр. 0.5 = середина элемента)
        show_G    -- вывод графа (по умолчанию: False)
        show_par  -- вывод параметров (по умолчанию: False)
        kaskade   -- каскадное удаление (по умолчанию: False)

    Возвращает:
        submdl -- подмодель с добавленным узлом КЗ (не рассчитана)

    Исключения:
        ValueError -- если элемент не найден или не содержит ветвей
    """
    elem = next((e for e in mdl.be if str(e.name) == str(elem_name)), None)
    if elem is None:
        raise ValueError(f'Элемент {elem_name!r} не найден в модели')
    if not elem.plist:
        raise ValueError(f'Элемент {elem_name!r} не содержит ветвей')

    # Длины ветвей — модуль |Z1| как суррогат физической длины
    lengths = [abs(p.Z[0]) for p in elem.plist]
    total = sum(lengths) or 1.0
    target = float(percent) * total

    cum = 0.0
    for i, p in enumerate(elem.plist):
        cum += lengths[i]
        if cum >= target - 1e-9 or i == len(elem.plist) - 1:
            branch_percent = ((target - (cum - lengths[i])) / lengths[i]
                              if lengths[i] > 0 else 0.5)
            branch_percent = max(0.0, min(1.0, branch_percent))
            return kz_q(mdl, line=p, percentage_of_line=branch_percent,
                        show_G=show_G, show_par=show_par, kaskade=kaskade)
