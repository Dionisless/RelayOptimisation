# -*- coding: utf-8 -*-
'''МОДУЛЬ РАСЧЕТА ТОКОВ КОРОТКОГО ЗАМЫКАНИЯ (М Р Т К З)

Версия 3.15

г.Саратов 27.01.2021

История изменений
27.01.2021
- Рефакторинг кода, исключено применение промежуточного массива для суммирования
  B/2 подключенных к узлу ветвей и собственной Y узла;
- Реализован метод позволяющий выявить висящие, не связанные с землей узлы, ветви,
  взаимоиндукции и несимметрии что в приводит к вырожденности (сингулярности)
  формируемой СЛАУ, т.е. к невозможности решения СЛАУ.
  Параллельные ветви с нулевым сопротивлением (ШСВ и  СВ), также приводят к
  вырожденности, но данный метод не позволяет их выявить!,
  для предотвращения вырожденности можно предложить использовать некоторое
  сопротивление на СВ и ШСВ вместо 0, например 0.001 Ом.
  mdl.Test4Singularity();
- Выявлена и устранена логическая ошибка в условии вывода результатов токов
  в проводимости узла.

22.01.2021
- С учетом реализации возможности ввода проводимости в узле скорректирован вывод
  результатов расчетов расчета по узлу
- В таблицах вывода результатов заменен знак < на знак ∠

18.01.2021
- Реализована поддержка проводимостей Y (См) подключенных к узлу, например компенсирующих
  реакторов (ранее, да и сейчас их можно также представить ветвями на землю);
- Реализована поддержка источников тока J(А), что необходимо для учета в схеме
  замещения сети ветровых и солнечных электростанция и других ЭС со звеном
  постоянного тока с последующим инвертированием к промышленной частоте 50 Гц.
  Q(model,name,Y=(Y1,Y2,Y0))
  Q(model,name,J=(J1,J2,J0))
  Q(model,name,Y=(Y1,Y2,Y0),J=(J1,J2,J0))

03.12.2020
- Оптимизирован метод mdl.Calc, в части понижения потребляемой памяти и повышения
  быстродействия, за счет отказа от использования списков python для формирования
  координатной разреженной матрицы, вместо этого используются вектора numpy;
- Произведен переход на расчет фазных, междуфазных (линейных) и прочих величин
  с помощью матричного умножения результатов в симметричных составляющих на
  преобразующие матрицы (Ms2f - для вычисления фазных величин, Ms2ff - для
  вычисления междуфазных (линейных) величин);
- При формировании разреженной матрицы в ходе перебора типов несимметрий для
  повышения быстродействия на первое место поставлены КЗ 'N0' и обрыв 'N0'
  как наиболее часто встречающиеся в модели;
- Оптимизирован код, по выводу результатов расчетов, изменен порядок вывода
  результата, сначала идут фазные значения, потом симметричные составляющие
  и наконец междуфазные (линейные) величины. Уменьшено дублирование кода.

28.11.2020
1. В класс Model добавлен метод ImportFromPVL(PVL_Sech), предназначенный для
   импорта результатов расчетов параметров схемы замещения ВЛ с помощью модуля PVL
   mdl.ImportFromPVL(PVL_Sech)
   где PVL_Sech - ссылка на сечение (объект класса sech модуля PVL)

18.11.2020
1. Добавлены описания к функциям, классам и методам МРТКЗ,
    в том числе дано подробное описание алгоритма метода mdl.Calc()
2. Добавлены специальные нeсимметрии вида:
    - КЗ по нулевой последовательности - 'N0' для моделирования заземления нейтрали за
      трансформатором Yg/D или за соответствующей парой обмоток тр-ра
    - Обрыв по нулевой последовательности - 'N0' для моделирования сети с изолированной
      нейтралью, устанавливается на ветви разделяющей сеть с глухо или эффективно
      заземленной нейтралью и сетью с изолированной нейтралью
3. Выверено моделирование ветвей с поперечной емкостной проводимостью B,
    для этого если pl62w+ или аналогичное ПО выдает (Например)
    B1 = В2 = 90 мкСм (1/Ом*10^-6), B0 = 60 мкСм (1/Ом*10^-6)
    то при создании ветви надо заполнять параметры емкостной проводимости
    B=(90e-6j,90e-6j,60e-6j)
4. Выверено моделирование трансформаторных ветвей
    T=(Ktrans,GrT) - безразмерные параметры трансформаторной ветви:
    Ktrans - коэффициент трансформации силового трансформатора, например 115/11
    GrT - группа обмоток обмотки подключенной к узлу 2 (от 0 до 11)
    Так например для трансформатора с номинальными напряжениями обмоток 115 и 10,5 кВ
    и схемой соединения обмоток Y/D-11 надо заполнять параметры трансформаторной ветви
    T=(115/10.5,11)
5. Добавлены новые методы класса Model
    - AddNQ для группового добавления узлов (сечения узлов)
    mdl.AddNQ(NQ,Nname)
    где NQ - количество создаваемых узлов
        Nname - общее имя узлов, к уникальному имени узлу будет добавляться
        номер из сечения от 1 до NQ
    - AddNP для группового добавления ветвей (сечения ветвей)
    в том числе с поперечной емкостной проводимостью B и
    взаимоиндукцией нулевой последовательности
    mdl.AddNP(self,Nname,listq1,listq2,Z12,Z0) - без учета емкостной проводимости
    mdl.AddNP(self,Nname,listq1,listq2,Z12,Z0,B12,B0) - с учетом емкостной проводимости
    где listq1 и listq2 - сечения (списки) узлов
        Nname - общее имя сечения ветвей, к уникальному имени ветви будет добавляться
        номер из сечения от 1 до N, где N - количество создаваемых ветвей
        Z12 - вектор numpy.ndarray значений сопротивлений ветвей прямой/обратной последовательности
        Z0 - квадратная матрица numpy.ndarray значений сопротивлений ветвей и
            взаимоиндукций нулевой последовательности
        B12 - вектор numpy.ndarray значений поперечной емкостной проводимости
            прямой/обратной последовательности
        B0 - квадратная матрица numpy.ndarray значений поперечной емкостной
            проводимости нулевой последовательности
'''
import networkx as nx
import matplotlib.pyplot as plt

import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import spsolve

Kf = -1j*np.pi/6
r2d = 180/np.pi
a =  -0.5 + 0.5j*np.sqrt(3)
a2 = -0.5 - 0.5j*np.sqrt(3)
a0 = 1.0+0.0j
vA = np.array([a0,a0,a0])
vB = np.array([a2,a ,a0])
vC = np.array([a, a2,a0])
vAB = vA - vB
vBC = vB - vC
vCA = vC - vA
vABC = np.concatenate((vA,vB,vC))
vBCA = np.concatenate((vB,vC,vA))
vCAB = np.concatenate((vC,vA,vB))
Ms2f = np.array([vA,vB,vC])
Ms2ff = np.array([vAB,vBC,vCA])
arr012 = np.array([0,1,2])
arr000 = np.array([0,0,0])
arr111 = arr000+1
arr222 = arr000+2
arr_111 = -arr111


class Q:
    '''Класс трехфазного электрического узла, необходим для формирования расчетной
    модели и получения результатов расчета

    Создание узла с помощью конструктора
    Q(model,name,desc='')
    Q(model,name)
    где:
       model - объект расчетной модели в которой создается узел
       name - краткое название узла, обращение к узлу по его имени не предусмотрено
       desc - Примечание или любая другая текстовая информация, можно не задавать.
    Результатом конструктора узла является объект узла, который используется для
    формирования расчетной модели и вывода результатов расчетов

    Пользовательские функции для объекта узла q
    Вывод на экран параметров узла - его номера и названия
    q.par()

    Вывод сводной таблицы результатов расчетов для узла q
    q.res()

    Вывод конкретного параметра ParName в виде компексного числа
    для последующего использования в расчетах
    q.res(ParName)
    где ParName может принимать значения:
    'U1','U2','U0','3U0','UA','UB','UC','UABC','UAB','UBC','UCA','UAB_BC_CA'

    Вывод конкретного параметра ParName в заданной форме Form:
    q.res(ParName,Form)
    где Form может принимать значения
    'R' - Активная составляющая
    'X' - Реактивная составляющая
    'M' - Модуль комплексного числа
    '<f' - Фаза вектора в градусах
    'R+jX' - Текстовый вид комплексного числа
    'M<f' - Текстовый вид комплексного числа

    Еще один способ получения конкректного параметра результата в виде
        компексного числа для его последующего использования в расчетах
        q.ParName
        где ParName может принимать значения:
        U1,U2,U0,UA,UB,UC,UABC,UAB,UBC,UCA,UAB_BC_CA'''
    def __init__(self,model,name,Y=(0,0,0),J=(0,0,0),desc='',x=0,y=0):
        ''' Конструктор объекта узла
        Q(model,name,desc='')
        Q(model,name)
        Q(model,name,Y=(Y1,Y2,Y0))
        Q(model,name,J=(J1,J2,J0))
        Q(model,name,Y=(Y1,Y2,Y0),J=(J1,J2,J0))
        где:
           model - объект расчетной модели в которой создается узел
           name - краткое название узла, обращение к узлу по его имени не предусмотрено
           Y = (Y1,Y2,Y0) - проводимость в узле на землю, См
           J = (J1,J2,J0) - источник тока подключенный к узлу, А
               (положительное направление источника тока - "в узел")
           desc - Примечание или любая другая текстовая информация, можно не задавать.
        Результатом конструктора узла является объект узла, который используется для
        формирования расчетной модели и вывода результатов расчетов'''
        if not isinstance(model, Model):
            raise TypeError('Ошибка при добавлении узла -', name, '\n',
                            'Аргумент model должен иметь тип Model!')
        model.nq += 1
        model.bq.append(self)
        self.id = model.nq
        self.model = model
        self.name = name
        self.Y = Y
        self.J = J
        self.desc = desc
        self.plist = []
        self.kn = None
        self.x = x
        self.y = y
        # добавляет узел в граф
        G_node = model.G.add_node(name,pos=(x,y))
        self.G = G_node
        
#    def __del__(self):
#        print('q_del')
    def edit_coords(self,x,y):
        '''Изменить координаты узла можно с помощью метода
        q.edit_coords(x,y)'''
        self.x = x
        self.y = y
        # обновляет координаты узла в графе
        self.model.G.nodes[self.name]['pos'] = (x, y)
        
    def info(self):
        # выводит информацию об узле
        q_info = { 
            'q_id': self.id,
            'model': self.model,
            'q_name': self.name,
            'q_Y': self.Y,
            'q_J': self.J,
            'q_text':self.desc,
#            'plist':self.plist,
            'is_kn':self.kn,
            'q_x':self.x,
            'q_y':self.y
    }
        return q_info

    
    def Test4Singularity(self):
        if self.singulare:
            self.singulare = False
            for pk in self.plist:
                if pk.q1 is pk.q2:
                    pass
                elif pk.q1 is self:
                    if isinstance(pk.q2, Q):
                        pk.q2.Test4Singularity()
                elif pk.q2 is self:
                    if isinstance(pk.q1, Q):
                        pk.q1.Test4Singularity()



    def addp(self,kp):
        '''Служебный метод, предназачен для информирования узла о подключенных к нему ветвей'''
        self.plist.append(kp)

    def update(self):
        '''Служебный метод, предназачен для проверки информации о подключенных к узлу ветвей'''
        temp_plist = self.plist
        self.plist = []
        for kp in temp_plist:
            if (kp.q1 is self) or (kp.q2 is self):
                self.plist.append(kp)

    def setn(self,kn):
        '''Служебный метод, предназачен для информирования узла о наличии КЗ в данном узле'''
        self.kn = kn

    def par(self):
        '''Вывод на экран параметров узла - его номера и названия'''
        print('Узел №', self.id, ' - ', self.name)

    def getres(self):
        '''Служебный метод, возвращает результат расчета по данному узлу -
        напряжения прямой, обратной и нулевой последовательностей, тоже что и q.res('U120')'''
        if self.model is None:
            raise ValueError('Ошибка при выводе результатов расчетов Узла №', self.id, ' - ', self.name, '\n',
                            'Узел не принадлежит какой либо модели!')
        if self.model.X is None:
            raise ValueError('Ошибка при выводе результатов расчетов Узла №', self.id, ' - ', self.name, '\n',
                            'Не произведен расчет электрических величин!')
        qId = 3*(self.model.np+self.id-1)
        return self.model.X[qId:qId+3]

    def res(self,parnames='',subpar=''):
        '''Вывод сводной таблицы результатов расчетов для узла q
        q.res()

        Вывод конкретного параметра ParName в виде компексного числа
        для последующего использования в расчетах
        q.res(ParName)
        где ParName может принимать значения:
        'U1','U2','U0','3U0','UA','UB','UC','UABC','UAB','UBC','UCA','UAB_BC_CA'

        Вывод конкретного параметра ParName в заданной форме Form:
        q.res(ParName,Form)
        где Form может принимать значения
        'R' - Активная составляющая
        'X' - Реактивная составляющая
        'M' - Модуль комплексного числа
        '<f' - Фаза вектора в градусах
        'R+jX' - Текстовый вид комплексного числа
        'M<f' - Текстовый вид комплексного числа'''
        u120 = self.getres()
        i120 = np.array(self.Y) * u120
        if parnames=='':
            print('Узел № {} - {}'.format(self.id, self.name))
            print(StrU(u120))
            if (i120 != np.zeros(3)).any():
                print("Значения токов проводимости узла")
                print(StrI(i120))
        else:
            results={}
            for parname in parnames:
                res = mselectz[parname](u120,i120)
                if isinstance(res, np.ndarray):
                    res = mform3[subpar](res,parname)
                else:
                    res = mform1[subpar](res,parname)
                results[parname] = res
                
            return results
            

    def __getattr__(self, attrname):
        '''Еще один способ получения конкректного параметра результата в виде
        компексного числа для его последующего использования в расчетах
        q.ParName
        где ParName может принимать значения:
        U1,U2,U0,UA,UB,UC,UABC,UAB,UBC,UCA,UAB_BC_CA'''
        u120 = self.getres()
        i120 = np.array(self.Y) * u120
        return mselectz[attrname](u120,i120)

    def kar_res(self):
        '''Еще один способ получения конкректного параметра результата в виде
        компексного числа для его последующего использования в расчетах
        q.ParName
        где ParName может принимать значения:
        U1,U2,U0,UA,UB,UC,UABC,UAB,UBC,UCA,UAB_BC_CA'''
        u120 = self.getres()
        i120 = np.array(self.Y) * u120
        return u120,i120

#    def kar_q_clear(self):
        '''очистка узла'''



    
    def __repr__(self):
        '''Еще один способ вывода сводной таблицы результатов расчетов для узла q
        В командной строке интерпретара набрать название переменной объекта узла и нажать Enter
        q Enter'''
        u120 = self.getres()
        i120 = np.array(self.Y) * u120
        strres = []
        strres.append("Узел № {} - {}\n".format(self.id, self.name))
        strres.append(StrU(u120))
        if (i120 != np.zeros(3)).any():
            strres.append("Значения токов проводимости узла")
            strres.append(StrI(i120))
        return ''.join(strres)


class P:
    '''Класс трехфазной ветви, необходим для формирования расчетной модели
    и получения результатов расчета

    Создание ветви с помощью конструктора
    P(model,name,q1,q2,Z) - простая ветвь
    P(model,name,q1,q2,Z,desc='Примечание') - ветвь с текстовым примечанием
    P(model,name,q1,q2,Z,E=(E1,E2,E0)) - ветвь представляющая энергосистему, генератор (Вольт - фазные)
    P(model,name,q1,q2,Z,B=(B1,B2,B0)) - ветвь c наличием поперечной емкостной проводимостью B/2 (См)
    P(model,name,q1,q2,Z,T=(Ktrans,GrT)) - ветвь представляющая трансформатор
    где:
       model - объект расчетной модели в которой создается ветвь
       name - краткое название ветви, обращение к ветви по ее имени не предусмотрено
       q1,q2 - число 0, что означает подключение ветви соответствующим концом к земле,
               объект узла принадлежащего той же расчетной модели
       desc - Примечание или любая другая текстовая информация, можно не задавать.
       Z=(Z1,Z2,Z0) - комплексные сопротивление ветви (Ом) прямой, обратной и нулевой последовательностей
       E=(E1,E2,E0) - комплексные фазные значения Э.Д.С. (Вольт) прямой, обратной и нулевой последовательностей
       B=(B1,B2,B0) - комплексные значения поперечной емкостной проводимости B (См)
                       прямой, обратной и нулевой последовательностей,
                       если pl62w+ или аналогичная выдает Например
                       B1 = В2 = 90 мкСм (1/Ом*10^-6), B0 = 60 мкСм (1/Ом*10^-6)
                       то при создании ветви надо заполнять параметры ветви
                       B=(90e-6j,90e-6j,60e-6j)
       T=(Ktrans,GrT) - безразмерные параметры трансформаторной ветви:
          Ktrans - коэффициент трансформации силового трансформатора
          GrT - группа обмоток обмотки подключенной к узлу 2 (от 0 до 11)

    Результатом конструктора ветви является объект ветви, который используется для
    формирования расчетной модели и вывода результатов расчетов

    Изменить параметры ветви p можно с помощью метода
    p.edit(name,q1,q2,Z)
    p.edit(name,q1,q2,Z,desc='Примечание')
    p.edit(name,q1,q2,Z,E=(E1,E2,E0))
    p.edit(name,q1,q2,Z,B=(B1,B2,B0))
    p.edit(name,q1,q2,Z,T=(Ktrans,GrT))

    Пользовательские функции для объекта ветви p
    Вывод на экран параметров ветви - ее номера, названия, номеров и наименований узлов к которым она подключена,
    электрических параметров Z,E,B и T
    p.par()

    Вывод сводной таблицы результатов расчетов для ветви p
    со стороны 1-ого и 2-ого узла соответственно (направление токов и пр. в линию)
    p.res1()
    p.res2()

    Вывод конкретного параметра ParName в виде компексного числа
    для последующего использования в расчетах
    со стороны 1-ого и 2-ого узла соответственно (направление токов и пр. в линию)
    p.res1(ParName)
    p.res2(ParName)
    где ParName может принимать значения:
    'U1','U2','U0','3U0','UA','UB','UC','UABC','UAB','UBC','UCA','UAB_BC_CA',
    'I1','I2','I0','3I0','IA','IB','IC','IABC','IAB','IBC','ICA','IAB_BC_CA',
    'Z1','Z2','Z0','ZA','ZB','ZC','ZABC','ZAB','ZBC','ZCA','ZAB_BC_CA',
    'S1','S2','S0','SA','SB','SC','SABC','SAB','SBC','SCA','SAB_BC_CA','S'

    Вывод конкретного параметра ParName в заданной форме Form:
    p.res1(ParName,Form)
    p.res2(ParName,Form)
    где Form может принимать значения
    'R' - Активная составляющая
    'X' - Реактивная составляющая
    'M' - Модуль комплексного числа
    '<f' - Фаза вектора в градусах
    'R+jX' - Текстовый вид комплексного числа
    'M<f' - Текстовый вид комплексного числа


    Еще один способ получения конкректного параметра результата в виде
    компексного числа для его последующего использования в расчетах
    p.ParName
    где ParName может принимать значения:
    значения токов от 1-ого ко 2-ому узлу без учета емкостной проводимости
    I1,I2,I0,I120,IA,IB,IC,IABC,IAB,IBC,ICA,IAB_BC_CA
    со стороны 1-ого узла
    q1U1,q1U2,q1U0,q1U120,q1UA,q1UB,q1UC,q1UABC,q1UAB,q1UBC,q1UCA,q1UAB_BC_CA,
    q1I1,q1I2,q1I0,q1I120,q1IA,q1IB,q1IC,q1IABC,q1IAB,q1IBC,q1ICA,q1IAB_BC_CA,
    q1Z1,q1Z2,q1Z0,q1Z120,q1ZA,q1ZB,q1ZC,q1ZABC,q1ZAB,q1ZBC,q1ZCA,q1ZAB_BC_CA,
    q1S1,q1S2,q1S0,q1S120,q1SA,q1SB,q1SC,q1SABC,q1SAB,q1SBC,q1SCA,q1SAB_BC_CA,q1S
    со стороны 2-ого узла
    q2U1,q2U2,q2U0,q1U120,q2UA,q2UB,q2UC,q2UABC,q2UAB,q2UBC,q2UCA,q2UAB_BC_CA,
    q2I1,q2I2,q2I0,q1I120,q2IA,q2IB,q2IC,q2IABC,q2IAB,q2IBC,q2ICA,q2IAB_BC_CA,
    q2Z1,q2Z2,q2Z0,q1Z120,q2ZA,q2ZB,q2ZC,q2ZABC,q2ZAB,q2ZBC,q2ZCA,q2ZAB_BC_CA,
    q2S1,q2S2,q2S0,q1S120,q2SA,q2SB,q2SC,q2SABC,q2SAB,q2SBC,q2SCA,q2SAB_BC_CA,q2S
    '''
    def __init__(self,model,name,q1,q2,Z,E=(0, 0, 0),T=(1, 0),B=(0, 0, 0),desc=''):
        ''' Конструктор ветви
        P(model,name,q1,q2,Z) - простая ветвь
        P(model,name,q1,q2,Z,desc='Примечание') - ветвь с текстовым примечанием
        P(model,name,q1,q2,Z,E=(E1,E2,E0)) - ветвь представляющая энергосистему, генератор (Вольт - фазные)
        P(model,name,q1,q2,Z,B=(B1,B2,B0)) - ветвь c наличием поперечной емкостной проводимостью B/2 (См)
        P(model,name,q1,q2,Z,T=(Ktrans,GrT)) - ветвь представляющая трансформатор
        где:
           model - объект расчетной модели в которой создается ветвь
           name - краткое название ветви, обращение к ветви по ее имени не предусмотрено
           q1,q2 - число 0, что означает подключение ветви соответствующим концом к земле,
                   объект узла принадлежащего той же расчетной модели
           desc - Примечание или любая другая текстовая информация, можно не задавать.
           Z=(Z1,Z2,Z0) - комплексные сопротивление ветви (Ом) прямой, обратной и нулевой последовательностей
           E=(E1,E2,E0) - комплексные фазные значения Э.Д.С. (Вольт) прямой, обратной и нулевой последовательностей
           B=(B1,B2,B0) - комплексные значения поперечной емкостной проводимости B (См)
                           прямой, обратной и нулевой последовательностей,
                           если pl62w+ или аналогичная выдает Например
                           B1 = В2 = 90 мкСм (1/Ом*10^-6), B0 = 60 мкСм (1/Ом*10^-6)
                           то при создании ветви надо заполнять параметры ветви
                           B=(90e-6j,90e-6j,60e-6j)
           T=(Ktrans,GrT) - безразмерные параметры трансформаторной ветви:
              Ktrans - коэффициент трансформации силового трансформатора
              GrT - группа обмоток обмотки подключенной к узлу 2 (от 0 до 11)
        Результатом конструктора ветви является объект ветви, который используется для
        формирования расчетной модели и вывода результатов расчетов'''
        if not isinstance(model, Model):
            raise TypeError('Ошибка при добавлении ветви -', name, '\n',
                            'Аргумент model должен иметь тип Model!')
        if isinstance(q1, int):
            if q1 != 0:
                raise ValueError('Ошибка при добавлении ветви -', name, '\n',
                                 'Для подключения ветви к земле q1=0')
        elif isinstance(q1, Q):
            if not q1.model is model:
                raise ValueError('Ошибка при добавлении ветви -', name, '\n',
                                'Узел q1 должен принадлежать той-же модели!')
        else:
            raise TypeError('Ошибка при добавлении ветви -', name, '\n',
                            'Аргумент q1 должен иметь тип Q или int!')
        if isinstance(q2, int):
            if q2 != 0:
                raise ValueError('Ошибка при добавлении ветви -', name, '\n',
                                 'Для подключения ветви к земле q2=0')
        elif isinstance(q2, Q):
            if not q2.model is model:
                raise ValueError('Ошибка при добавлении ветви -', name, '\n',
                                'Узел q2 должен принадлежать той-же модели!')
        else:
            raise TypeError('Ошибка при добавлении ветви -', name, '\n',
                            'Аргумент q2 должен иметь тип Q или int!')
        if  q1 is q2:
            print('Предупреждение! при добавлении ветви -', name, '\n',
                            'Ветвь подключается обоими концами к одному и тому же узлу!')
        model.np += 1
        model.bp.append(self)
        self.id = model.np
        self.model = model
        self.name = name
        self.desc = desc
        self.q1 = q1
        if isinstance(q1, Q):
            q1.addp(self)
        self.q2 = q2
        if isinstance(q2, Q):
            q2.addp(self)
        self.Z = Z
        self.E = E
        self.T = T
        self.B = B
        self.mlist = []
        self.kn = None
        self.nq1_def = 0
        self.nq2_def = 0
        self.q1_def = []
        self.q2_def =[]

#        if E!=0:
#            node_color = 'red'
        
        # добавляет линию в граф
        if (q1!=0 and q2!=0):
            self.G = model.G.add_edge(q1.name,q2.name, name=name)
            model.G.add_edge(q1.name,q2.name, name=name)
            
        # добавляет линию в граф если второй узел - земля
        elif q1==0:

            g_node = model.G.add_node(name+'_0', pos=((q2.x+0.25), (q2.y-0.5)), name=name)
            self.G = model.G.add_edge(name+'_0', q2.name, name=name)
            model.G.add_edge(name+'_0', q2.name, name=name)
 #           g_name = name + 'gr'
            locals()[name + 'gr'] = g_node
        else:
            g_node = model.G.add_node(name+'_0', pos=((q1.x+0.25), (q1.y-0.5)), name=name)
            self.G = model.G.add_edge(name+'_0', q1.name, name=name)
            model.G.add_edge(name+'_0', q1.name, name=name)
 #           g_name = name + 'gr'
            locals()[name + 'gr'] = g_node
            
#Удаление ветви, пока хз работает ли
 #   def delete_p(self):
  #      q1 = self.q1
   #     q2 = self.q2
    #    del self
     #   q1.update()
      #  q2.update()

#    def __del__(self):
#        print('Line delited')
    
    def info(self):
        # выводит информацию о ветви (P)
        p_info = {
        'p_id': self.id,
        'model': self.model,
        'p_name': self.name,
        'p_text': self.desc,
        'q1': self.q1.name if self.q1 else None,
        'q2': self.q2.name if self.q2 else None,
        'p_Z': self.Z,
        'p_E': self.E,
        'p_T': self.T,
        'p_B': self.B,
        # 'mlist': self.mlist,
        'is_kn': self.kn
        }
        return p_info
    
    def edit(self,name,q1,q2,Z,E=(0, 0, 0),T=(1, 0),B=(0, 0, 0),desc=''):
        '''Изменить параметры ветви можно с помощью метода
        p.edit(name,q1,q2,Z)
        p.edit(name,q1,q2,Z,desc='Примечание')
        p.edit(name,q1,q2,Z,E=(E1,E2,E0))
        p.edit(name,q1,q2,Z,B=(B1,B2,B0))
        p.edit(name,q1,q2,Z,T=(Ktrans,GrT))'''
        if isinstance(q1, int):
            if q1 != 0:
                raise ValueError('Ошибка при редактировании ветви №', self.id, ' - ', self.name, '\n',
                                 'Для подключения ветви к земле q1=0')
        elif isinstance(q1, Q):
            if not q1.model is self.model:
                raise ValueError('Ошибка при редактировании ветви №', self.id, ' - ', self.name, '\n',
                                'Узел q1 должен принадлежать той-же модели!')
        else:
            raise TypeError('Ошибка при редактировании ветви №', self.id, ' - ', self.name, '\n',
                            'Аргумент q1 должен иметь тип Q или int!')
        if isinstance(q2, int):
            if q2 != 0:
                raise ValueError('Ошибка при редактировании ветви №', self.id, ' - ', self.name, '\n',
                                 'Для подключения ветви к земле q2=0')
        elif isinstance(q2, Q):
            if not q2.model is self.model:
                raise ValueError('Ошибка при редактировании ветви №', self.id, ' - ', self.name, '\n',
                                'Узел q2 должен принадлежать той-же модели!')
        else:
            raise TypeError('Ошибка при редактировании ветви №', self.id, ' - ', self.name, '\n',
                            'Аргумент q2 должен иметь тип Q или int!')
        if  q1 is q2:
            print('Предупреждение! при добавлении ветви -', name, '\n',
                            'Ветвь подключается обоими концами к одному и тому же узлу!')
        self.name = name
        self.desc = desc
        self.q1 = q1
        if isinstance(q1, Q):
            q1.addp(self)
            q1.update()
        self.q2 = q2
        if isinstance(q2, Q):
            q2.addp(self)
            q2.update()
        self.Z = Z
        self.E = E
        self.T = T
        self.B = B

    def addm(self,mid):
        '''Служебный метод, предназачен для информирования ветви
        о подключенных к ней взаимоиндуктивностей'''
        self.mlist.append(mid)

    def setn(self,kn):
        '''Служебный метод, предназачен для информирования ветви
        о наличии на ней обрыва'''
        self.kn=kn

    def par(self):
        '''Вывод на экран параметров ветви - ее номера, названия, номеров и наименований узлов к которым она подключена,
        электрических параметров Z,E,B и T
        p.par()'''
        if isinstance(self.q1, Q):
            q1id = self.q1.id
            q1name = self.q1.name
        else:
            q1id = 0; q1name = 'Земля'
        if isinstance(self.q2, Q):
            q2id = self.q2.id
            q2name = self.q2.name
        else:
            q2id = 0
            q2name = 'Земля'
        print('Ветвь № {} - {} : {}({}) <=> {}({})'.format(self.id,self.name,q1id,q1name,q2id,q2name))
        print('Z = {}; E = {}; T = {}; B = {}'.format(self.Z,self.E,self.T,self.B))


    
    def getres(self):
        '''Служебный метод, возвращает результат расчета по данной ветви
        без учета наличия поперечной проводимости и направления от узла 1 к узлу 2
        токов прямой, обратной и нулевой последовательностей, тоже что и p.res1('U120') если B=0'''
        if self.model is None:
            raise ValueError('Ошибка при выводе результатов расчетов Ветви №', self.id, ' - ', self.name, '\n',
                            'Ветвь не принадлежит какой либо модели!')
        if self.model.X is None:
            raise ValueError('Ошибка при выводе результатов расчетов Ветви №', self.id, ' - ', self.name, '\n',
                            'Не произведен расчет электрических величин!')
        pId = 3*(self.id-1)
        return self.model.X[pId:pId+3]

    def getresq1(self,i120):
        '''Служебный метод, возвращает результат расчета по данной ветви
        c учетом наличия поперечной проводимости и направления от узла 1 к узлу 2
        токов прямой, обратной и нулевой последовательностей, тоже что и p.res1('U120')'''
        if isinstance(self.q1, Q):
            u120 = self.q1.getres()
            i120 += u120 * self.B/2
        else:
            u120 = np.zeros(3,dtype=complex)
        return [u120, i120]

    def getresq2(self,i120):
        '''Служебный метод, возвращает результат расчета по данной ветви
        c учетом наличия поперечной проводимости и направления от узла 2 к узлу 1
        токов прямой, обратной и нулевой последовательностей, тоже что и p.res2('U120')'''
        if isinstance(self.q2, Q):
            u120 = self.q2.getres()
        else:
            u120 = np.zeros(3,dtype=complex)
        Kt = self.T[0]*np.exp(Kf*self.T[1]*np.ones(3))
        if self.T[1] % 2 != 0:
            Kt[1] = np.conj(Kt[1])
        i120 = -Kt * i120 + u120 * self.B/2
        return [u120, i120]

    def res1(self,parnames='',subpar=''):
        '''Вывод сводной таблицы результатов расчетов для ветви p
        со стороны 1-ого узла (направление токов и пр. в линию)
        p.res1()

        Вывод конкретного параметра ParName в виде компексного числа
        для последующего использования в расчетах
        со стороны 1-ого узла (направление токов и пр. в линию)
        p.res1(ParName)
        где ParName может принимать значения:
        'U1','U2','U0','3U0','UA','UB','UC','UABC','UAB','UBC','UCA','UAB_BC_CA',
        'I1','I2','I0','3I0','IA','IB','IC','IABC','IAB','IBC','ICA','IAB_BC_CA',
        'Z1','Z2','Z0','ZA','ZB','ZC','ZABC','ZAB','ZBC','ZCA','ZAB_BC_CA',
        'S1','S2','S0','SA','SB','SC','SABC','SAB','SBC','SCA','SAB_BC_CA','S'

        Вывод конкретного параметра ParName в заданной форме Form:
        p.res1(ParName,Form)
        где Form может принимать значения
        'R' - Активная составляющая
        'X' - Реактивная составляющая
        'M' - Модуль комплексного числа
        '<f' - Фаза вектора в градусах
        'R+jX' - Текстовый вид комплексного числа
        'M<f' - Текстовый вид комплексного числа '''
        i120 = self.getres()
        if isinstance(self.q1, Q):
            q1id = self.q1.id
            q1name = self.q1.name
        else:
            q1id = 0
            q1name = 'Земля'
        u120,i120 = self.getresq1(i120)
        if parnames=='':
            print("Ветвь № {} - {}".format(self.id, self.name))
            print("Значения токов по ветви со стороны узла №{} - {}".format(q1id, q1name))
            print(StrI(i120))
            print("Значения напряжения в узле №{} - {}".format(q1id, q1name))
            print(StrU(u120))
        else:
            results={}
            for parname in parnames:
                res = mselectz[parname](u120,i120)
                if isinstance(res, np.ndarray):
                    res = mform3[subpar](res,parname)
                else:
                    res = mform1[subpar](res,parname)
                results[parname] = res
                
            return results

    def res2(self,parnames='',subpar=''):
        '''Вывод сводной таблицы результатов расчетов для ветви p
        со стороны 2-ого узла (направление токов и пр. в линию)
        p.res1()

        Вывод конкретного параметра ParName в виде компексного числа
        для последующего использования в расчетах
        со стороны 2-ого узла (направление токов и пр. в линию)
        p.res2(ParName)
        где ParName может принимать значения:
        'U1','U2','U0','3U0','U120','UA','UB','UC','UABC','UAB','UBC','UCA','UAB_BC_CA',
        'I1','I2','I0','3I0','I120','IA','IB','IC','IABC','IAB','IBC','ICA','IAB_BC_CA',
        'Z1','Z2','Z0','Z120','ZA','ZB','ZC','ZABC','ZAB','ZBC','ZCA','ZAB_BC_CA',
        'S1','S2','S0','S120','SA','SB','SC','SABC','SAB','SBC','SCA','SAB_BC_CA','S'

        Вывод конкретного параметра ParName в заданной форме Form:
        p.res2(ParName,Form)
        где Form может принимать значения
        'R' - Активная составляющая
        'X' - Реактивная составляющая
        'M' - Модуль комплексного числа
        '<f' - Фаза вектора в градусах
        'R+jX' - Текстовый вид комплексного числа
        'M<f' - Текстовый вид комплексного числа '''
        i120 = self.getres()
        if isinstance(self.q2, Q):
            q2id = self.q2.id
            q2name = self.q2.name
        else:
            q2id = 0
            q2name = 'Земля'
        u120,i120 = self.getresq2(i120)
        if parnames=='':
            print("Ветвь № {} - {}".format(self.id, self.name))
            print("Значения токов по ветви со стороны узла №{} - {}".format(q2id, q2name))
            print(StrI(i120))
            print("Значения напряжения в узле №{} - {}".format(q2id, q2name))
            print(StrU(u120))
        else:
            results={}
            for parname in parnames:
                res = mselectz[parname](u120,i120)
                if isinstance(res, np.ndarray):
                    res = mform3[subpar](res,parname)
                else:
                    res = mform1[subpar](res,parname)
                results[parname] = res
                
            return results

    
    def __repr__(self):
        '''Еще один способ вывода сводной таблицы результатов расчетов для ветви p
        В командной строке интерпретара набрать название переменной объекта ветви и нажать Enter
        p Enter, выводятся результаты с обоих концов ветви'''
        i120p = self.getres()
        if isinstance(self.q1, Q):
            q1id = self.q1.id
            q1name = self.q1.name
        else:
            q1id = 0
            q1name = 'Земля'
        u120,i120 = self.getresq1(i120p)
        strres = []
        strres.append("Ветвь № {} - {}\n".format(self.id, self.name))
        strres.append("Значения токов по ветви со стороны узла №{} - {}\n".format(q1id, q1name))
        strres.append(StrI(i120))
        strres.append("Значения напряжения в узле №{} - {}\n".format(q1id, q1name))
        strres.append(StrU(u120))
        if isinstance(self.q2, Q):
            q2id = self.q2.id
            q2name = self.q2.name
        else:
            q2id = 0
            q2name = 'Земля'
        u120,i120 = self.getresq2(i120p)
        strres.append("Значения токов по ветви со стороны узла №{} - {}\n".format(q2id, q2name))
        strres.append(StrI(i120))
        strres.append("Значения напряжения в узле №{} - {}\n".format(q2id, q2name))
        strres.append(StrU(u120))
        return (''.join(strres))

    def __getattr__(self, attrname):
        '''Еще один способ получения конкректного параметра результата в виде
        компексного числа для его последующего использования в расчетах
        p.ParName
        где ParName может принимать значения:
        значения токов от 1-ого ко 2-ому узлу без учета емкостной проводимости
        I1,I2,I0,I120,IA,IB,IC,IABC,IAB,IBC,ICA,IAB_BC_CA
        со стороны 1-ого узла
        q1U1,q1U2,q1U0,q1U120,q1UA,q1UB,q1UC,q1UABC,q1UAB,q1UBC,q1UCA,q1UAB_BC_CA,
        q1I1,q1I2,q1I0,q1I120,q1IA,q1IB,q1IC,q1IABC,q1IAB,q1IBC,q1ICA,q1IAB_BC_CA,
        q1Z1,q1Z2,q1Z0,q1Z120,q1ZA,q1ZB,q1ZC,q1ZABC,q1ZAB,q1ZBC,q1ZCA,q1ZAB_BC_CA,
        q1S1,q1S2,q1S0,q1S120,q1SA,q1SB,q1SC,q1SABC,q1SAB,q1SBC,q1SCA,q1SAB_BC_CA,q1S
        со стороны 2-ого узла
        q2U1,q2U2,q2U0,q1U120,q2UA,q2UB,q2UC,q2UABC,q2UAB,q2UBC,q2UCA,q2UAB_BC_CA,
        q2I1,q2I2,q2I0,q1I120,q2IA,q2IB,q2IC,q2IABC,q2IAB,q2IBC,q2ICA,q2IAB_BC_CA,
        q2Z1,q2Z2,q2Z0,q1Z120,q2ZA,q2ZB,q2ZC,q2ZABC,q2ZAB,q2ZBC,q2ZCA,q2ZAB_BC_CA,
        q2S1,q2S2,q2S0,q1S120,q2SA,q2SB,q2SC,q2SABC,q2SAB,q2SBC,q2SCA,q2SAB_BC_CA,q2S'''
        i120p = self.getres()
        if not attrname[:2] in ('q1', 'q2'):
            res = mselectz[attrname](np.zeros(3),i120p)
        elif attrname[:2] == 'q1':
            u120,i120 = self.getresq1(i120p)
            res = mselectz[attrname[2:]](u120,i120)
        elif attrname[:2] == 'q2':
            u120,i120 = self.getresq2(i120p)
            res = mselectz[attrname[2:]](u120,i120)
        return res

class protection:

    '''Класс ступени релейной (пока только ТЗНП) защиты, относится к узлу q линии p, симулируя нахождение в выключателе линии. 

    Создание ветви с помощью конструктора
    protection(self, p, q, type='ТЗНП', stage, I0, t, P_rnm=0, rnm_base_angle=0, stage_on = True, I0_range=[300,3000], t_range=[0,20], desc='')
    
    где:
       model - объект расчетной модели в которой создается ветвь
       p - объект линии на которой находится РЗ
       q - узел РЗ
       type - тип линии
       stage - номер ступени
       I0 - уставка по току нулевой последовательности
       P_rnm - мощность срабатывания реле направления мощности
       rnm_base_angle - угол макс срабатывания реле напр мощности, при 0 - выведена
       stage_on - выведена ли ступень
       I0_range, t_range - границы изменения уставок реле
       desc - что-нибудь написать 


    также реализованны методы:
        self.rnm_on - выведено ли реле направления мощности
        

 '''   
    def __init__(self, p, q, stage, I0, t, stat_id='',type='ТЗНП', P_rnm=0, rnm_base_angle=0, stage_on = True, rnm_on = False, I0_range=[300,3000], t_range=[0,20], desc='', k_ch=0.83, k_ots=1.2, k_voz=0.85):

        if p.q1==q:
            p.q1_def.append(self)
            p.nq1_def += 1
            self.nq = 'q1'
            self.id = p.nq1_def
        elif p.q2==q: 
            p.q2_def.append(self)
            p.nq1_def += 1
            self.nq = 'q2'
            self.id = p.nq2_def
        else: print('Ошибка: в линии p нет узла q')
        
        p.model.nd += 1
        p.model.bd.append(self)
        self.id = p.model.nd
        if stat_id=='': self.stat_id = self.id
        else: self.stat_id = stat_id
        self.model = p.model
        self.p = p
        self.q = q
        self.type = 'ТЗНП'
        self.stage = stage
        self.I0 = I0
        self.t = t
        self.P_rnm = P_rnm
        self.rnm_on = rnm_on
        self.rnm_ang = rnm_base_angle
        self.stage_on = stage_on
        self.I0_range = I0_range
        self.t_range = t_range
        self.desc = desc
        self.k_ch = k_ch
        self.k_ots = k_ots
        self.k_voz = k_voz
        
    def edit(self, I0, t, stage_on = True):
        #Изменить уставки защиты можно с помощью метода
        self.I0 = I0
        self.t = t
    


class M:
    '''Класс взаимоиндукции нулевой последовательности,
    необходим для формирования расчетной модели

    Создание ветви с помощью конструктора
    M(model,name,p1,p2,M12,M21) - взаимоиндукция
    M(model,name,p1,p2,M12,M21,desc='Примечание') - взаимоиндукция с текстовым примечанием
    где:
       model - объект расчетной модели в которой создается взаимоиндукция
       name - краткое название взаимоиндукции, обращение к ветви по ее имени не предусмотрено
       p1,p2 - объекты ветви принадлежащего той же расчетной модели между которыми создается взаимоиндукция
       desc - Примечание или любая другая текстовая информация, можно не задавать.
       M12 - взаимоиндукция влияния ветви p2 на ветвь p1
       M21 - взаимоиндукция влияния ветви p1 на ветвь p2

    Результатом конструктора ветви является объект взаимоиндукции, который используется для
    формирования расчетной модели

    Изменить параметры взаимоиндукции m можно с помощью метода
    m.edit(name,M12,M21)

    Пользовательские функции для объекта взаимоиндукции m
    Вывод на экран параметров ветви - ее номера, названия, номеров и наименований ветвей
    между которыми создана взаимоиндукция, электрических параметров M12,M21
    m.par()'''
    def __init__(self,model,name,p1,p2,M12,M21,desc=''):
        ''' Конструктор взаимоиндукции
        Создание ветви с помощью конструктора
        M(model,name,p1,p2,M12,M21) - взаимоиндукция
        M(model,name,p1,p2,M12,M21,desc='Примечание') - взаимоиндукция с текстовым примечанием
        где:
           model - объект расчетной модели в которой создается взаимоиндукция
           name - краткое название взаимоиндукции, обращение к ветви по ее имени не предусмотрено
           p1,p2 - объекты ветви принадлежащего той же расчетной модели между которыми создается взаимоиндукция
           desc - Примечание или любая другая текстовая информация, можно не задавать.
           M12 - взаимоиндукция влияния ветви p2 на ветвь p1
           M21 - взаимоиндукция влияния ветви p1 на ветвь p2
        '''
        if not isinstance(model, Model):
            raise TypeError('Ошибка при добавлении взаимоиндукции -', name, '\n',
                            'Аргумент model должен иметь тип Model!')
        if not isinstance(p1, P):
            raise TypeError('Ошибка при добавлении взаимоиндукции -', name, '\n',
                            'Аргумент p1 должен иметь тип P!')
        if not isinstance(p2, P):
            raise TypeError('Ошибка при добавлении взаимоиндукции -', name, '\n',
                            'Аргумент p2 должен иметь тип P!')
        if not p1.model is model:
            raise ValueError('Ошибка при добавлении взаимоиндукции -', name, '\n',
                            'Ветвь p1 должна принадлежать той-же модели!')
        if not p2.model is model:
            raise ValueError('Ошибка при добавлении взаимоиндукции -', name, '\n',
                            'Ветвь p2 должна принадлежать той-же модели!')
        if  p1 is p2:
            raise ValueError('Ошибка при добавлении взаимоиндукции -', name, '\n',
                            'Взаимоиндукция подключается к одной и той же ветви!')
        model.nm += 1
        model.bm.append(self)
        self.id = model.nm
        self.model = model
        self.name = name
        self.desc = desc
        self.p1 = p1
        p1.addm(self)
        self.p2 = p2
        p2.addm(self)
        self.M12 = M12
        self.M21 = M21

    def edit(self,name,M12,M21):
        ''' Редактирование взаимоиндукции
        m.edit(model,name,M12,M21)'''
        self.name = name
        self.M12 = M12
        self.M21 = M21

    def par(self):
        '''Вывод на экран параметров ветви - ее номера, названия, номеров и наименований ветвей
        между которыми создана взаимоиндукция, электрических параметров M12,M21
        m.par()'''
        print('Взаимоиндукция № {} - {} : {}({}) <=> {}({})'.format(self.id,self.name,self.p1.id,self.p1.name,self.p2.id,self.p2.name))
        print('M12 = {}; M21 = {}'.format(self.M12,self.M21))

class N:
    '''Класс продольной (обрыв) или поперечной (КЗ) несимметрии,
    необходим для формирования расчетной модели и получения результатов расчета

    Создание несимметрии с помощью конструктора
    N(model,name,qp,SC) - несимметрия
    N(model,name,qp,SC,desc='Примечание') - несимметрия с текстовым примечанием
    N(model,name,qp,SC,r=Rd) - несимметрия в виде КЗ с переходным сопротивлением
    где:
       model - объект расчетной модели в которой создается несимметрия
       name - краткое название несимметрии, обращение к несимметрии по ее имени не предусмотрено
       qp - объект узла (КЗ) или ветви (обрыв) в котором создается несимметрия
       desc - Примечание или любая другая текстовая информация, можно не задавать.
       SC - вид КЗ, обрыва может принимать значения:
           'A0','B0','C0' - металлические однофазные КЗ на землю или обрыв соответствующей фазы
           'A0r','B0r','C0r' - однофазные КЗ на землю через переходное сопротивление
           'AB','BC','CA' - металлические двухфазные КЗ  или обрыв соответствующих фаз
           'ABr','BCr','CAr' - двухфазные КЗ через переходное сопротивление
           'AB0','BC0','CA0' - металлические двухфазные КЗ на землю
           'ABC' - трехфазное КЗ без земли  или обрыв трех фаз
           'ABC0' - трехфазное КЗ на землю
           'N0' - Заземление в узле в схеме нулевой последовательности
                  или обрыв по нулевой последовательности на ветви

    Результатом конструктора несимметрии является объект несимметрии, который используется для
    формирования расчетной модели и вывода результатов расчетов

    Изменить параметры несимметрии n можно с помощью метода
    n.edit(name,SC)
    n.edit(name,SC,desc='')
    n.edit(name,SC,r=0)

    Пользовательские функции для объекта несимметрии n
    Вывод на экран параметров несимметрии - ее номера, названия,
    номера и наименования узла или ветви к которым она подключена,
    вида несимметрии
    n.par()

    Вывод сводной таблицы результатов расчетов для несимметрии n
    n.res()

    Вывод конкретного параметра ParName в виде компексного числа
    для последующего использования в расчетах
    n.res(ParName)
    где ParName может принимать значения:
    'U1','U2','U0','3U0','U120','UA','UB','UC','UABC','UAB','UBC','UCA','UAB_BC_CA',
    'I1','I2','I0','3I0','I120','IA','IB','IC','IABC','IAB','IBC','ICA','IAB_BC_CA',
    'Z1','Z2','Z0','Z120','ZA','ZB','ZC','ZABC','ZAB','ZBC','ZCA','ZAB_BC_CA',
    'S1','S2','S0','S120','SA','SB','SC','SABC','SAB','SBC','SCA','SAB_BC_CA','S'

    Вывод конкретного параметра ParName в заданной форме Form:
    n.res(ParName,Form)
    где Form может принимать значения
    'R' - Активная составляющая
    'X' - Реактивная составляющая
    'M' - Модуль комплексного числа
    '<f' - Фаза вектора в градусах
    'R+jX' - Текстовый вид комплексного числа
    'M<f' - Текстовый вид комплексного числа


    Еще один способ получения конкректного параметра результата в виде
    компексного числа для его последующего использования в расчетах
    n.ParName
    где ParName может принимать значения:
    U1,U2,U0,UA,UB,UC,UABC,UAB,UBC,UCA,UAB_BC_CA
    I1,I2,I0,IA,IB,IC,IABC,IAB,IBC,ICA,IAB_BC_CA
    Z1,Z2,Z0,Z120,ZA,ZB,ZC,ZABC,ZAB,ZBC,ZCA,ZAB_BC_CA,
    S1,S2,S0,S120,SA,SB,SC,SABC,SAB,SBC,SCA,SAB_BC_CA,S'''
    def __init__(self,model,name,qp,SC,r=0,desc=''):
        ''' Конструктор повреждения (КЗ или обрыва)'''
        if not isinstance(model, Model):
            raise TypeError('Ошибка при добавлении несимметрии -', name, '\n',
                            'Аргумент model должен иметь тип Model!')
        if not isinstance(qp, (Q,P)):
            raise TypeError('Ошибка при добавлении несимметрии -', name, '\n',
                            'Аргумент qp должен иметь тип Q или P!')
        if not qp.model is model:
            raise ValueError('Ошибка при добавлении несимметрии -', name, '\n',
                            'Узел/Ветвь qp должны принадлежать той-же модели!')
        model.nn += 1
        model.bn.append(self)
        self.id = model.nn
        self.model = model
        self.name = name
        self.desc = desc
        self.qp = qp
        qp.setn(self)
        self.SC = SC
        self.r = r

    def edit(self, name,SC,r=0,desc=''):
        '''Изменить параметры несимметрии n можно с помощью метода
        n.edit(name,SC)
        n.edit(name,SC,desc='')
        n.edit(name,SC,r=0)'''
        self.name = name
        self.desc = desc
        self.SC = SC
        self.r = r

    def par(self):
        '''Вывод на экран параметров несимметрии - ее номера, названия,
        номера и наименования узла или ветви к которым она подключена,
        вида несимметрии
        n.par()'''
        if isinstance(self.qp, Q):
            print('КЗ № {} - {} : {} (r={}) в узле № {}({})'.format(self.id,self.name,self.SC,self.r,self.qp.id,self.qp.name))
        elif isinstance(self.qp, P):
            print('Обрыв № {} - {} : {} на ветви № {}({})'.format(self.id,self.name,self.SC,self.qp.id,self.qp.name))

    def getres(self):
        '''Служебный метод, возвращает результат расчета по данной несимметрии
        для КЗ - токи КЗ прямой, обратной и нулевой последовательностей;
        для обрывов - напряжения продольной несимметрии прямой, обратной и нулевой последовательностей.'''
        if self.model is None:
            raise ValueError('Ошибка при выводе результатов расчетов несимметрии №', self.id, ' - ', self.name, '\n',
                            'Несимметрия не принадлежит какой либо модели!')
        if self.model.X is None:
            raise ValueError('Ошибка при выводе результатов расчетов несимметрии №', self.id, ' - ', self.name, '\n',
                            'Не произведен расчет электрических величин!')
        nId = 3*(self.model.np+self.model.nq+self.id-1)
        return self.model.X[nId:nId+3]

    def res(self,parname='',subpar=''):
        '''Вывод сводной таблицы результатов расчетов для несимметрии n
        n.res()

        Вывод конкретного параметра ParName в виде компексного числа
        для последующего использования в расчетах
        n.res(ParName)
        где ParName может принимать значения:
        'U1','U2','U0','3U0','U120','UA','UB','UC','UABC','UAB','UBC','UCA','UAB_BC_CA',
        'I1','I2','I0','3I0','I120','IA','IB','IC','IABC','IAB','IBC','ICA','IAB_BC_CA',
        'Z1','Z2','Z0','Z120','ZA','ZB','ZC','ZABC','ZAB','ZBC','ZCA','ZAB_BC_CA',
        'S1','S2','S0','S120','SA','SB','SC','SABC','SAB','SBC','SCA','SAB_BC_CA','S'

        Вывод конкретного параметра ParName в заданной форме Form:
        n.res(ParName,Form)
        где Form может принимать значения
        'R' - Активная составляющая
        'X' - Реактивная составляющая
        'M' - Модуль комплексного числа
        '<f' - Фаза вектора в градусах
        'R+jX' - Текстовый вид комплексного числа
        'M<f' - Текстовый вид комплексного числа'''
        if isinstance(self.qp, Q):
            u120 = self.qp.getres()
            i120 = self.getres()
            if parname=='':
                print('КЗ № {} - {} - {}'.format(self.id, self.name, self.SC))
                print('В Узле № {} - {}'.format(self.qp.id, self.qp.name))
                print(StrU(u120))
                print('Суммарный ток КЗ в Узле № {} - {}'.format(self.qp.id, self.qp.name))
                print(StrI(i120))
                print('Подтекание токов по ветвям')
                self.qp.update()
                for kp in self.qp.plist:
                    i120 = kp.getres()
                    if self.qp is kp.q1:
                        u120,i120 = kp.getresq1(i120)
                    elif self.qp is kp.q2:
                        u120,i120 = kp.getresq2(i120)
                    i120 = -i120
                    print('Ветвь № {} - {}'.format(kp.id, kp.name))
                    print(StrI(i120, 0))
            else:
                res = mselectz[parname](u120,i120)
                if isinstance(res, np.ndarray):
                    res = mform3[subpar](res,parname)
                else:
                    res = mform1[subpar](res,parname)
                return res

    def __repr__(self):
        '''Еще один способ вывода сводной таблицы результатов расчетов для несимметрии n
        В командной строке интерпретара набрать название переменной объекта несимметрии n и нажать Enter
        n Enter'''
        if isinstance(self.qp, Q):
            u120 = self.qp.getres()
            i120 = self.getres()
            strres = []
            strres.append('КЗ №{} - {} - {}\n'.format(self.id, self.name, self.SC))
            strres.append('В Узле № {} - {}\n'.format(self.qp.id, self.qp.name))
            strres.append(StrU(u120))
            strres.append('\nСуммарный ток КЗ в Узле № {} - {}\n'.format(self.qp.id, self.qp.name))
            strres.append(StrI(i120))
            strres.append('\nПодтекание токов по ветвям')

            for kp in self.qp.plist:
                i120p = kp.getres()
                if self.qp is kp.q1:
                    _,i120p = kp.getresq1(i120p)
                elif self.qp is kp.q2:
                    _,i120p = kp.getresq2(i120p)
                i120p = -i120p
                strres.append('\nВетвь № {} - {}\n'.format(kp.id, kp.name))
                strres.append(StrI(i120p,0))
            strres = ''.join(strres)
        elif isinstance(self.qp, P):
            strres = self.qp.__repr__()
        return (strres)

    def __getattr__(self, attrname):
        '''Еще один способ получения конкректного параметра результата в виде
        компексного числа для его последующего использования в расчетах
        n.ParName
        где ParName может принимать значения:
        U1,U2,U0,UA,UB,UC,UABC,UAB,UBC,UCA,UAB_BC_CA
        I1,I2,I0,IA,IB,IC,IABC,IAB,IBC,ICA,IAB_BC_CA
        Z1,Z2,Z0,Z120,ZA,ZB,ZC,ZABC,ZAB,ZBC,ZCA,ZAB_BC_CA,
        S1,S2,S0,S120,SA,SB,SC,SABC,SAB,SBC,SCA,SAB_BC_CA,S'''
        if isinstance(self.qp, Q):
            u120 = self.qp.getres()
            i120 = self.getres()
        elif isinstance(self.qp, P):
            u120 = self.getres()
            i120 = self.qp.getres()
        res = mselectz[attrname](u120,i120)
        return res

''' Инструментальная функция, для превращения имени переменной в строку'''
def var2str(var, vars_data = locals()):
    return [var_name for var_name in vars_data if id(var) == id(vars_data[var_name])]

#exec("%s = %d" % (test_str, 10))

class Model:
    '''Класс представляющий расчетную модель электрической сети,
    необходим для формирования и хранения расчетной модели, выполнения расчетов

    Конструктор расчетной модели сети
    Model()
    Model(desc='Примечание')


    Пользовательские функции для модели mdl
    Обнуление количества и очистка списков (таблиц) узлов, ветвей,
    взаимоиндукций, несимметрий...
    mdl.Clear()'''
    def __init__(self,desc=''):
        ''' Конструктор расчетной модели'''
        self.desc = desc
        self.nq = 0
        self.np = 0
        self.nm = 0
        self.nn = 0
        self.nd = 0
        self.bq = []
        self.bp = []
        self.bm = []
        self.bn = []
        self.bd = []
        self.X = None
        self.G = nx.Graph()
    def AddNQ(self,NQ,Nname):
        '''Множественное создание узлов
        NQ - количество создаваемых узлов
        Nname - общее наименование узлов'''
        listq = []
        for ij in range(NQ):
            listq.append(Q(self,'{} - №{}'.format(Nname,ij+1)))
        return listq

    def AddNP(self,Nname,listq1,listq2,Z12,Z0,B12=None,B0=None):
        '''Множественное создание ветвей и взаимоиндуктивностей
        NQ - количество создаваемых узлов
        Nname - общее наименование сечения ветвей
        listq1 - список объектов узлов к которым буду подключаться ветви
        listq2 - другой список объектов узлов к которым буду подключаться ветви
        Z12 - вектор np.ndarray значений сопротивлений ветвей прямой/обратной последовательности
        Z0 - квадратная матрица np.ndarray значений сопротивлений ветвей и взаимоиндукций нулевой последовательности
        B12 - вектор np.ndarray значений поперечной емкостной проводимости прямой/обратной последовательности
        B0 - квадратная матрица np.ndarray значений поперечной емкостной проводимости нулевой последовательности
        AddNP(Nname,listq1,listq2,Z12,Z0) - при отсутствии поперечной емкостной проводимости
        AddNP(Nname,listq1,listq2,Z12,Z0,B12,B0) - при наличии поперечной емкостной проводимости'''
        listp = []
        listm = []
        nq1 = len(listq1)
        nq2 = len(listq2)
        if nq1 != nq2:
            raise ValueError('Ошибка при добавлении сечения ветвей -', Nname, '\n',
                            'Количество узлов с обоих сторон должно совпадать!')
        if not isinstance(Z12, np.ndarray):
            raise TypeError('Ошибка при добавлении сечения ветвей -', Nname, '\n',
                            'Аргумент Z12 должен иметь тип np.ndarray!')
        if not isinstance(Z0, np.ndarray):
            raise TypeError('Ошибка при добавлении сечения ветвей -', Nname, '\n',
                            'Аргумент Z0 должен иметь тип np.ndarray!')
        if nq1 != Z12.shape[0]:
            raise ValueError('Ошибка при добавлении сечения ветвей -', Nname, '\n',
                            'Количество сопротивлений Z12 должно соответствовать количеству узлов!')
        if nq1 != Z0.shape[0] or nq1 != Z0.shape[1]:
            raise ValueError('Ошибка при добавлении сечения ветвей -', Nname, '\n',
                            'Количество сопротивлений Z0 должно соответствовать количеству узлов!')
        if isinstance(B12, np.ndarray) and isinstance(B0, np.ndarray):
            if not isinstance(B12, np.ndarray):
                raise TypeError('Ошибка при добавлении сечения ветвей -', Nname, '\n',
                                'Аргумент B12 должен иметь тип np.ndarray!')
            if not isinstance(B0, np.ndarray):
                raise TypeError('Ошибка при добавлении сечения ветвей -', Nname, '\n',
                                'Аргумент B0 должен иметь тип np.ndarray!')
            if nq1 != B12.shape[0]:
                raise ValueError('Ошибка при добавлении сечения ветвей -', Nname, '\n',
                                'Количество сопротивлений B12 должно соответствовать количеству узлов!')
            if nq1 != B0.shape[0] or nq1 != B0.shape[1]:
                raise ValueError('Ошибка при добавлении сечения ветвей -', Nname, '\n',
                                'Количество сопротивлений B0 должно соответствовать количеству узлов!')
            for ij in range(nq1):
                #(self,model,name,q1,q2,Z,E=(0, 0, 0),T=(1, 0),B=(0, 0, 0),desc='')
                listp.append(P(self,'{} - №{}'.format(Nname,ij+1),listq1[ij],listq2[ij]),Z=(Z12[ij],Z12[ij],Z0[ij,ij]),B=(B12[ij],B12[ij],B0[ij,ij]))
                for ij2 in range(ij):
                    listm.append(M(self,'{} - №{}<=>№{}'.format(Nname,ij+1,ij2+1),listp[ij],listp[ij2],Z0[ij,ij2],Z0[ij2,ij]))
        else:
            for ij in range(nq1):
                listp.append(P(self,'{} - №{}'.format(Nname,ij+1),listq1[ij],listq2[ij]),Z=(Z12[ij],Z12[ij],Z0[ij,ij]))
                for ij2 in range(ij):
                    listm.append(M(self,'{} - №{}<=>№{}'.format(Nname,ij+1,ij2+1),listp[ij],listp[ij2],Z0[ij,ij2],Z0[ij2,ij]))
        return listp + listm

    def ImportFromPVL(self,PVL_Sech):
        '''Импорт сечений ветвей из PVL'''
        listp = []
        listm = []
        PVL_Sech.calc()
        z1 = PVL_Sech.Len * PVL_Sech.Z1
        z0 = PVL_Sech.Len * PVL_Sech.Z0
        b1 = PVL_Sech.Len * PVL_Sech.B1
        b0 = PVL_Sech.Len * PVL_Sech.B0
        for ij,pk in enumerate(PVL_Sech.bp):
            p1 = P(self, pk.name, pk.q1, pk.q2,
                   (z1[ij,0],z1[ij,0],z0[ij,ij]),
                   B=(b1[ij,0],b1[ij,0],b0[ij,ij]) )
            listp.append(p1)
            for ij2,pk2 in enumerate(PVL_Sech.bp[0:ij]):
                mname = '{} - №{}<=>№{}'.format(PVL_Sech.name,pk.name,pk2.name)
                p2 = listp[ij2]
                m = M(self,mname,p1,p2,z0[ij,ij2],z0[ij2,ij])
                listm.append(m)
        return listp + listm

    def Clear(self):
        '''Полная очистка расчетной модели
        Обнуление количества и очистка списков (таблиц) узлов, ветвей,
        взаимоиндукций, несимметрий...
        mdl.Clear()'''
        self.X = None
        self.nq = 0
        self.np = 0
        self.nm = 0
        self.nn = 0
        for kq in self.bq:
            kq.model = None
            kq.plist = []
            kq.kn = None
        for kp in self.bp:
            kp.model = None
            kp.q1 = None
            kp.q2 = None
            kp.mlist = []
            kp.kn = None
        for km in self.bm:
            km.model = None
            km.p1 = None
            km.p2 = None
        for kn in self.bn:
            kn.model = None
            kn.qp = None
        self.bq = []
        self.bp = []
        self.bm = []
        self.bn = []
        self.G.clear()

    def ClearN(self):
        '''Очистка всех несимметрий (КЗ и обрывов) в расчетной модели
        за исключением типа 'N0' - заземлений и обрывов по нулевой последовательности
        mdl.ClearN()'''
        self.X = None
        self.nn = 0
        oldbn = self.bn
        self.bn = []
        for kn in oldbn:
            if kn.SC == 'N0':
                self.nn += 1
                self.bn.append(kn)
                kn.id = self.nn
            else:
                kn.model = None
                kn.qp.kn = None

    def List(self):
        '''Вывод на экран составляющих расчетную модель узлов, ветвей,
        взаимоиндукций, несимметрий и их параметров...
        По сути является поочередным применением метода par() ко всем элементам
        расчетной модели
        mdl.List()'''
        print('Количество узлов = {}; ветвей = {}; взаимоиндуктивностей = {}; несимметрий = {}'.format(self.nq,self.np,self.nm,self.nn))
        for kq in self.bq:
            kq.par()
        for kp in self.bp:
            kp.par()
        for km in self.bm:
            km.par()
        for kn in self.bn:
            kn.par()

    def Test4Singularity(self):
        '''Тестирование модели на условия приводящие к вырожденности
        (сингулярности) матрицы уравнений узловых напряжений и токов ветвей
        mdl.Test4Singularity()'''
        for kq in self.bq:
            kq.singulare = True
        for kp in self.bp:
            if isinstance(kp.q1, int) and isinstance(kp.q2, Q):
                kp.q2.Test4Singularity()
            elif isinstance(kp.q1, Q) and isinstance(kp.q2, int):
                kp.q1.Test4Singularity()
        listq = []
        listp = []
        for kq in self.bq:
            if kq.singulare:
                listq.append(kq)
        for kp in self.bp:
            if (kp.q1 in listq) or (kp.q2 in listq):
                listp.append(kp)
        if listq or listp:
            print('\nСписок висящих узлов\n')
            for kq in listq:
                kq.par()
            print('\nСписок висящих ветвей\n')
            for kp in listp:
                kp.par()
            print('\nСписок взаимоиндукций между ветвями, хотя-бы одна из которых является висящей\n')
            for km in self.bm:
                if (km.p1 in listp) or (km.p2 in listp):
                    km.par()
            print('\nСписок КЗ на висящем узле или обрывов на висящих ветвях\n')
            for kn in self.bn:
                if isinstance(kn.qp, Q): # Короткие замыкания
                    if kn.qp in listq:
                        kn.par()
                if isinstance(kn.qp, P): # Обрывы
                    if kn.qp in listp:
                        kn.par()
            raise ValueError('Выявлены висящие узлы, ветви!!! \nВыполнение расчетов электрических параметров невозможно! \nУдалите или закоментируйте висящие узлы, ветви,\n, взаимоиндукции, КЗ и обрывы!')


    def Calc(self):
        '''Главный метод модуля МРТКЗ mdl.Calc()
        Осуществляет формирование разреженной системы линейных алгебраических уравнений (СЛАУ)
        и последующее ее решение с помощью алгоритма библиотеки scipy - spsolve(LHS,RHS)
        LHS * X = RHS
        где LHS - разреженная квадратная матрица
            RHS - вектор столбец
            X - искомый результат расчета
        Для каждого узла и ветви формируется по три уравнения:
            для схемы прямой, обратной и нулевой последовательностей
        Для каждой несимметрии формируется по три уравнения:
            уравнения граничных условий, определяющих несимметрию
        Размерность (количество уравнений) равняется 3*(np+nq+nn), где:
            np - количество ветвей в расчетной модели;
            nq - количество узлов в расчетной модели;
            nn - количество несимметрий в расчетной модели.
        Вышеуказанное уравнение представляет собой систему матричных уравнений
        без учета уравнений описывающих несимметрии:
            Z*Ip + At*Uq = E
            A*Ip + (-B/2)*Uq = -J
            где:
                1-ое уравнение сформировано по 2-ому закону Кирхгофа (Zp*Ip - (Uq1 - Uq2) = Ep)
                2-ое уравнение сформировано по 1-ому закону Кирхгофа (сумма токов в узле равна нулю)
                Z - квадратная матрица сопротивлений ветвей и взаимных индуктивностей
                прямой, обратной и нулевой последовательностей, размерность - (3*np,3*np)
                A - матрица соединений, размерность - (3*nq,3*np)
                At - транспонированная матрица соединений, размерность - (3*np,3*nq)
                (B/2) - квадратная диагональная матрица сумм поперечных проводимостей B/2,
                подключенных к узлу прямой, обратной и нулевой последовательностей, размерность - (3*nq,3*nq)
                E - вектор столбец Э.Д.С. ветвей прямой, обратной и нулевой последовательностей, размерность - (3*np,1)
                J - вектор столбец источников тока подключенных к узлам
                Ip - искомый вектор столбец значений токов ветвей
                прямой, обратной и нулевой последовательностей, размерность - (3*np,1)
                Uq - искомый вектор столбец значений напряжений узлов
                прямой, обратной и нулевой последовательностей, размерность - (3*nq,1)
            На каждую несимметрию дополнительно пишется по три уравнения -
            граничных условий (для понимания указаны в фазных величинах):
                Короткие замыкания
                А0 => Uka=0;Ikb=0;Ikc=0
                B0 => Ukb=0;Ikc=0;Ika=0
                C0 => Ukc=0;Ika=0;Ikb=0

                А0r => Uka-r*Ika=0;Ikb=0;Ikc=0
                B0r => Ukb-r*Ikb=0;Ikc=0;Ika=0
                C0r => Ukc-r*Ikc=0;Ika=0;Ikb=0

                АB => Uka-Ukb=0;Ika+Ikb=0;Ikc=0
                BC => Ukb-Ukc=0;Ikb+Ikc=0;Ika=0
                CА => Ukc-Uka=0;Ikc+Ika=0;Ikb=0

                АBr => Uka-Ukb-r*Ika=0;Ika+Ikb=0;Ikc=0
                BCr => Ukb-Ukc-r*Ikb=0;Ikb+Ikc=0;Ika=0
                CАr => Ukc-Uka-r*Ikc=0;Ikc+Ika=0;Ikb=0

                АB0 => Uka=0;Ukb=0;Ikc=0
                BC0 => Ukb=0;Ukc=0;Ika=0
                CА0 => Ukc=0;Uka=0;Ikb=0

                АBC => Uk1=0;Uk2=0;Ik0=0
                АBC0 => Uk1=0;Uk2=0;Uk0=0
                Заземление нейтрали N0 => Ik1=0;Ik2=0;Uk0=0

                Обрывы
                А0 => Ia=0;dUb=0;dUc=0
                B0 => Ib=0;dUc=0;dUa=0
                C0 => Ic=0;dUa=0;dUb=0

                АB => Ia=0;Ib=0;dUc=0
                BC => Ib=0;Ic=0;dUa=0
                CА => Ic=0;Ia=0;dUb=0

                АBC => I1=0;I2=0;I0=0
                Обрыв ветви по нулевой последовательности N0  => dU1=0;dU2=0;I0=0
            а также в новых столбцах по каждой из последовательностей прописывается:
                - Для КЗ в уравнение по 1-ому закону Кирхгофа
                A*Ip + (-B/2)*Uq - Ik = 0, где Ik - ток поперечной несимметрии
                - Для обрывов в уравнение по 2-ому закону Кирхгофа
                Z*Ip + At*Uq + dU = E, где dU - напряжение продольной несимметрии

        Разреженная матрица LHS формируется в два этапа
        Этап 1. формируется координатная версия резреженной матрицы в cdata, ri и ci,
        в которых хранятся значения ненулевых элеметнов матрицы, их номера строк и столбцов
        Этап 2. формируется CSC (Разреженный столбцовый формат) матрица LHS  с помощью метода scipy
        Решение разреженной СЛАУ осуществляется с помощью метода spsolve(LHS,RHS) библиотеки scipy'''
        # self.Test4Singularity()
        n = 3*(self.nq+self.np+self.nn)# Размерность СЛАУ
        maxnnz = 3*self.nq + 15*self.np + 2*self.nm + 15*self.nn# Максимальное кол-во ненулевых элементов разреженной матрицы
        RHS = np.zeros(n, dtype=complex)# Вектор правой части СЛАУ, в него записывается э.д.с. ветвей и J узлов

        ij = 3*self.nq # Текущий адрес записи, в результате количество использованной памяти
        cdata = np.zeros(maxnnz, dtype=np.cdouble)# Вектор для хранения ненулевых элементов СЛАУ
        ri = np.zeros(maxnnz, dtype=int)# Вектор для хранения номеров строк ненулевых элементов СЛАУ
        ci = np.zeros(maxnnz, dtype=int)# Вектор для хранения номеров столбцов ненулевых элементов СЛАУ
        ri[0:ij] = 3*self.np + np.arange(ij)
        ci[0:ij] = ri[0:ij]

        for kp in self.bp: # Перебор всех ветвей
            pId = 3*(kp.id-1)#Здесь и далее номер строки, столбца относящегося к прямой последовательности ветви
            lpId = pId+arr012#[pId,pId+1,pId+2]
            #Запись сопротивлений ветви в разреженную матрицу
            Dij = 3
            ri[ij:ij+Dij] = lpId
            ci[ij:ij+Dij] = lpId
            cdata[ij:ij+Dij] = np.array(kp.Z)
            ij += Dij
            #Запись Э.Д.С. ветви в RHS
            RHS[pId:pId+3] = np.array(kp.E)
            #Расчет комплексных коэф-ов трансформации прямой, обратной и нулевой последовательностей
            Kt1 = kp.T[0] * np.exp(Kf*kp.T[1])
            if kp.T[1] % 2 == 0:
                Kt2 = Kt1
            else:
                Kt2 = np.conj(Kt1)
            Kt0 = Kt1

            if isinstance(kp.q1, Q):
                qId = 3*(self.np + kp.q1.id - 1)#Здесь и далее номер строки, столбца относящегося к прямой последовательности узла
                lqId = qId+arr012#[qId,qId+1,qId+2]
                qbId = 3*(kp.q1.id-1)
                #Cуммирование B/2 подключенных ветвей к узлу
                cdata[qbId:qbId+3] -= np.array(kp.B)/2
                #Запись матриц соединений A и At в разреженную матрицу (для q1 -> -1)
                Dij = 6
                ri[ij:ij+Dij] = np.concatenate((lpId,lqId))#[pId,pId+1,pId+2,qId,qId+1,qId+2]
                ci[ij:ij+Dij] = np.concatenate((lqId,lpId))#[qId,qId+1,qId+2,pId,pId+1,pId+2]
                cdata[ij:ij+Dij] = np.concatenate((arr_111,arr_111))#[-1.0,-1.0,-1.0,-1.0,-1.0,-1.0]
                ij += Dij

            if isinstance(kp.q2, Q):
                qId = 3*(self.np + kp.q2.id - 1)
                lqId = qId+arr012#[qId,qId+1,qId+2]
                qbId = 3*(kp.q2.id-1)
                #Cуммирование B/2 подключенных ветвей к узлу
                cdata[qbId:qbId+3] -= np.array(kp.B)/2
                #Запись матриц соединений A и At в разреженную матрицу (для q2 -> 1 или Кт для трансформаторов)
                Dij = 6
                ri[ij:ij+Dij] = np.concatenate((lpId,lqId))#[pId,pId+1,pId+2,qId,qId+1,qId+2]
                ci[ij:ij+Dij] = np.concatenate((lqId,lpId))#[qId,qId+1,qId+2,pId,pId+1,pId+2]
                cdata[ij:ij+Dij] = np.array([Kt2,Kt1,Kt0,Kt1,Kt2,Kt0])
                ij += Dij

        for km in self.bm: # Перебор всех взаимоиндукций
            pId1 = 3*(km.p1.id-1)+2
            pId2 = 3*(km.p2.id-1)+2
            #Запись сопротивлений взаимоиндукции в разреженную матрицу
            Dij = 2
            ri[ij:ij+Dij] = np.array([pId1,pId2])
            ci[ij:ij+Dij] = np.array([pId2,pId1])
            cdata[ij:ij+Dij] = np.array([km.M12,km.M21])
            ij += Dij

        for kq in self.bq:# Перебор всех узлов
            qId = 3*(self.np + kq.id-1)
            qbId = 3*(kq.id-1)
            cdata[qbId:qbId+3] -= np.array(kq.Y)
            RHS[qId:qId+3] = -np.array(kq.J)

        for kn in self.bn: # Перебор всех несимметрий
            nId = 3*(self.nq+self.np+kn.id-1)#Здесь и далее номер строки, столбца относящегося к несимметрии
            lnId = nId + arr012
            if isinstance(kn.qp, Q): # Короткие замыкания
                qId = 3*(self.np+kn.qp.id-1)
                lqId = qId + arr012
                #Запись в разреженную матрицу в уравнения по 1-ому закону Кирхгофа наличие КЗ в узле
                Dij = 3
                ri[ij:ij+Dij] = lqId#[qId,qId+1,qId+2]
                ci[ij:ij+Dij] = lnId#[nId,nId+1,nId+2]
                cdata[ij:ij+Dij] = arr_111#[-1.0,-1.0,-1.0]
                ij += Dij
                if kn.SC=='N0' : #Заземление нейтрали Ik1=0;Ik2=0;Uk0=0
                    Dij = 3
                    ri[ij:ij+Dij] = lnId#[nId,nId+1,nId+2]
                    ci[ij:ij+Dij] = np.array([nId,nId+1,qId+2])
                    cdata[ij:ij+Dij] = vA#[1.0,1.0,1.0]
                    ij += Dij
                elif kn.SC in ('A0','B0','C0'):
                    #Запись в разреженную матрицу граничных условий для КЗ
                    Dij = 9
                    ri[ij:ij+Dij] = nId + np.concatenate((arr000,arr111,arr222))#[nId,nId,nId,nId+1,nId+1,nId+1,nId+2,nId+2,nId+2]
                    ci[ij:ij+Dij] = np.concatenate((lqId,lnId,lnId))#[qId,qId+1,qId+2,nId,nId+1,nId+2,nId,nId+1,nId+2]
                    if kn.SC == 'A0':# Uka=0;Ikb=0;Ikc=0
                        cdata[ij:ij+Dij] = vABC#[1.0,1.0,1.0,a2,a,1.0,a,a2,1.0]
                    elif kn.SC == 'B0':# Ukb=0;Ikc=0;Ika=0
                        cdata[ij:ij+Dij] = vBCA#[a2,a,1.0,1.0,1.0,1.0,a,a2,1.0]
                    else : # 'C0' # Ukc=0;Ika=0;Ikb=0
                        cdata[ij:ij+Dij] = vCAB#[a,a2,1.0,1.0,1.0,1.0,a2,a,1.0]
                    ij += Dij
                elif kn.SC in ('A0r','B0r','C0r'):
                    Dij = 12
                    ri[ij:ij+Dij] = nId + np.concatenate((arr000,arr111,arr222,arr000))#[nId,nId,nId,nId+1,nId+1,nId+1,nId+2,nId+2,nId+2,nId,nId,nId]
                    ci[ij:ij+Dij] = np.concatenate((lqId,lnId,lnId,lnId))#[qId,qId+1,qId+2,nId,nId+1,nId+2,nId,nId+1,nId+2,nId,nId+1,nId+2]
                    if kn.SC == 'A0r':# Uka-r*Ika=0;Ikb=0;Ikc=0
                        cdata[ij:ij+Dij] = np.concatenate((vABC, -kn.r*vA))#np.array(vA+vB+vC+[-kn.r,-kn.r,-kn.r])
                    elif kn.SC == 'B0r':# Ukb-r*Ikb=0;Ikc=0;Ika=0
                        cdata[ij:ij+Dij] = np.concatenate((vBCA, -kn.r*vB))#np.array(vB+vC+vA+[-kn.r*a2,-kn.r*a,-kn.r])#
                    else : # 'C0r'# Ukc-r*Ikc=0;Ika=0;Ikb=0
                        cdata[ij:ij+Dij] = np.concatenate((vCAB, -kn.r*vC))#np.array(vC+vA+vB+[-kn.r*a,-kn.r*a2,-kn.r])
                    ij += Dij
                elif kn.SC in ('AB','BC','CA'):
                    Dij = 5
                    ri[ij:ij+Dij] = nId + np.array([0,0,1,1,2])
                    ci[ij:ij+Dij] = np.array([qId,qId+1,nId,nId+1,nId+2])
                    if kn.SC == 'AB':# Uka-Ukb=0;Ika+Ikb=0;Ikc=0
                        cdata[ij:ij+Dij] = np.array([1.0-a2,1.0-a,1.0+a2,1.0+a,1.0])
                    elif kn.SC == 'BC':# Ukb-Ukc=0;Ikb+Ikc=0;Ika=0
                        cdata[ij:ij+Dij] = np.array([a2-a,a-a2,a2+a,a+a2,1.0])
                    else : # 'CA'# Ukc-Uka=0;Ikc+Ika=0;Ikb=0
                        cdata[ij:ij+Dij] = np.array([a-1.0,a2-1.0,a+1.0,a2+1.0,1.0])
                    ij += Dij
                elif kn.SC in ('ABr','BCr','CAr'):
                    Dij = 7
                    ri[ij:ij+Dij] = nId + np.array([0,0,1,1,2,0,0])
                    ci[ij:ij+Dij] = np.array([qId,qId+1,nId,nId+1,nId+2,nId,nId+1])
                    if kn.SC == 'ABr':# Uka-Ukb-r*Ika=0;Ika+Ikb=0;Ikc=0
                        cdata[ij:ij+Dij] = np.array([1.0-a2,1.0-a,1.0+a2,1.0+a,1.0,-kn.r,-kn.r])
                    elif kn.SC == 'BCr':# Ukb-Ukc-r*Ikb=0;Ikb+Ikc=0;Ika=0
                        cdata[ij:ij+Dij] = np.array([a2-a,a-a2,a2+a,a+a2,1.0,-kn.r*a2,-kn.r*a])
                    else : # 'CAr'# Ukc-Uka-r*Ikc=0;Ikc+Ika=0;Ikb=0
                        cdata[ij:ij+Dij] = np.array([a-1.0,a2-1.0,a+1.0,a2+1.0,1.0,-kn.r*a,-kn.r*a2])
                    ij += Dij
                elif kn.SC in ('AB0','BC0','CA0'):
                    Dij = 9
                    ri[ij:ij+Dij] = nId + np.concatenate((arr000,arr111,arr222))#np.array([nId,nId,nId,nId+1,nId+1,nId+1,nId+2,nId+2,nId+2])
                    ci[ij:ij+Dij] = np.concatenate((lqId,lqId,lnId))#np.array([qId,qId+1,qId+2,qId,qId+1,qId+2,nId,nId+1,nId+2])
                    if kn.SC == 'AB0':# Uka=0;Ukb=0;Ikc=0
                        cdata[ij:ij+Dij] = vABC#[1.0,1.0,1.0,a2,a,1.0,a,a2,1.0]
                    elif kn.SC == 'BC0':# Ukb=0;Ukc=0;Ika=0
                        cdata[ij:ij+Dij] = vBCA#[a2,a,1.0,a,a2,1.0,1.0,1.0,1.0]
                    else : # 'CA0'# Ukc=0;Uka=0;Ikb=0
                        cdata[ij:ij+Dij] = vCAB#[a,a2,1.0,1.0,1.0,1.0,a2,a,1.0]
                    ij += Dij
                elif kn.SC == 'ABC':# Uk1=0;Uk2=0;Ik0=0
                    Dij = 3
                    ri[ij:ij+Dij] = lnId#[nId,nId+1,nId+2]
                    ci[ij:ij+Dij] = np.array([qId,qId+1,nId+2])
                    cdata[ij:ij+Dij] = vA#[1.0,1.0,1.0]
                    ij += Dij
                elif kn.SC == 'ABC0' : # Uk1=0;Uk2=0;Uk0=0
                    Dij = 3
                    ri[ij:ij+Dij] = lnId#[nId,nId+1,nId+2]
                    ci[ij:ij+Dij] = lqId#[qId,qId+1,qId+2]
                    cdata[ij:ij+Dij] = vA#[1.0,1.0,1.0]
                    ij += Dij
                else :
                    raise TypeError('Неизвестный вид КЗ!')

            elif  isinstance(kn.qp, P): #Обрывы
                pId = 3*(kn.qp-1)
                lpId = pId+arr012
                #Запись в разреженную матрицу в уравнения по 2-ому закону Кирхгофа о наличии обрыва на ветви
                Dij = 3
                ri[ij:ij+Dij] = lpId#[pId,pId+1,pId+2]
                ci[ij:ij+Dij] = lnId#[nId,nId+1,nId+2]
                cdata[ij:ij+Dij] = vA#[1.0,1.0,1.0]
                ij += Dij
                if kn.SC == 'N0': #Обрыв ветви по нулевой последовательности dU1=0;dU2=0;I0=0
                    Dij = 3
                    ri[ij:ij+Dij] = lnId#[nId, nId+1, nId+2]
                    ci[ij:ij+Dij] = np.array([nId, nId+1, pId+2])
                    cdata[ij:ij+Dij] = vA#[1.0,1.0,1.0]
                    ij += Dij
                elif kn.SC in ('A0','B0','C0'):
                    Dij = 9
                    ri[ij:ij+Dij] = nId + np.concatenate((arr000,arr111,arr222))#[nId,nId,nId,nId+1,nId+1,nId+1,nId+2,nId+2,nId+2]
                    ci[ij:ij+Dij] = np.concatenate((lpId,lnId,lnId))#[pId,pId+1,pId+2,nId,nId+1,nId+2,nId,nId+1,nId+2]
                    if kn.SC == 'A0':# Ia=0;dUb=0;dUc=0
                        cdata[ij:ij+Dij] = vABC#[1.0,1.0,1.0,a2,a,1.0,a,a2,1.0]
                    elif kn.SC=='B0':# Ib=0;dUc=0;dUa=0
                        cdata[ij:ij+Dij] = vBCA#[a2,a,1.0,a,a2,1.0,1.0,1.0,1.0]
                    else : # 'C0'# Ic=0;dUa=0;dUb=0
                        cdata[ij:ij+Dij] = vCAB#[a,a2,1.0,1.0,1.0,1.0,a2,a,1.0]
                    ij += Dij
                elif kn.SC in ('AB','BC','CA'):
                    Dij = 9
                    ri[ij:ij+Dij] = nId + np.concatenate((arr000,arr111,arr222))#[nId,nId,nId,nId+1,nId+1,nId+1,nId+2,nId+2,nId+2]
                    ci[ij:ij+Dij] = np.concatenate((lpId,lpId,lnId))#[pId,pId+1,pId+2,pId,pId+1,pId+2,nId,nId+1,nId+2]
                    if kn.SC == 'AB':# Ia=0;Ib=0;dUc=0
                        cdata[ij:ij+Dij] = vABC#[1.0,1.0,1.0,a2,a,1.0,a,a2,1.0]
                    elif kn.SC == 'BC':# Ib=0;Ic=0;dUa=0
                        cdata[ij:ij+Dij] = vBCA#[a2,a,1.0,a,a2,1.0,1.0,1.0,1.0]
                    else : # 'CA'# Ic=0;Ia=0;dUb=0
                        cdata[ij:ij+Dij] = vCAB#[a,a2,1.0,1.0,1.0,1.0,a2,a,1.0]
                    ij += Dij
                elif kn.SC == 'ABC'  : # I1=0;I2=0;I0=0
                    Dij = 3
                    ri[ij:ij+Dij] = lnId#[nId, nId+1, nId+2]
                    ci[ij:ij+Dij] = lpId#[pId, pId+1, pId+2]
                    cdata[ij:ij+Dij] = vA#[1.0,1.0,1.0]
                    ij += Dij
                else: raise TypeError('Неизвестный вид обрыва!')
            else: raise TypeError('Неизвестный вид несимметрии!')
        #Формирование CSC разреженной матрицы (Разреженный столбцовый формат)
        LHS = csc_matrix((cdata[0:ij], (ri[0:ij], ci[0:ij])), shape=(n, n))
        #решение разреженной СЛАУ с помощью функции из состава scipy
        self.X = spsolve(LHS,RHS)
        return self.X

mselectz=dict({'U120' : lambda uq,ip: uq,
              'U1' : lambda uq,ip: uq[0],
              'U2' : lambda uq,ip: uq[1],
              'U0' : lambda uq,ip: uq[2],
              '3U0' : lambda uq,ip: 3*uq[2],
              'UA' : lambda uq,ip: vA @ uq,
              'UB' : lambda uq,ip: vB @ uq,
              'UC' : lambda uq,ip: vC @ uq,
              'UAB' : lambda uq,ip: vAB @ uq,
              'UBC' : lambda uq,ip: vBC @ uq,
              'UCA' : lambda uq,ip: vCA @ uq,
              'UABC' : lambda uq,ip: Ms2f @ uq,
              'UAB_BC_CA' : lambda uq,ip: Ms2ff @ uq,
              'I120' : lambda uq,ip: ip,
              'I1' : lambda uq,ip: ip[0],
              'I2' : lambda uq,ip: ip[1],
              'I0' : lambda uq,ip: ip[2],
              '3I0' : lambda uq,ip: 3*ip[2],
              'IA' : lambda uq,ip: vA @ ip,
              'IB' : lambda uq,ip: vB @ ip,
              'IC' : lambda uq,ip: vC @ ip,
              'IAB' : lambda uq,ip: vAB @ ip,
              'IBC' : lambda uq,ip: vBC @ ip,
              'ICA' : lambda uq,ip: vCA @ ip,
              'IABC' : lambda uq,ip: Ms2f @ ip,
              'IAB_BC_CA' : lambda uq,ip: Ms2ff @ ip,
              'Z120' : lambda uq,ip: uq / ip,
              'Z1' : lambda uq,ip: uq[0] / ip[0],
              'Z2' : lambda uq,ip: uq[1] / ip[1],
              'Z0' : lambda uq,ip: uq[2] / ip[2],
              'ZA' : lambda uq,ip: (vA @ uq) / (vA @ ip),
              'ZB' : lambda uq,ip: (vB @ uq) / (vB @ ip),
              'ZC' : lambda uq,ip: (vC @ uq) / (vC @ ip),
              'ZAB' : lambda uq,ip: (vAB @ uq) / (vAB @ ip),
              'ZBC' : lambda uq,ip: (vBC @ uq) / (vBC @ ip),
              'ZCA' : lambda uq,ip: (vCA @ uq) / (vCA @ ip),
              'ZABC' : lambda uq,ip: (Ms2f @ uq) / (Ms2f @ ip),
              'ZAB_BC_CA' : lambda uq,ip: (Ms2ff @ uq) / (Ms2ff @ ip),
              'S120' : lambda uq,ip: uq * np.conj(ip),
              'S1' : lambda uq,ip: uq[0] * np.conj(ip[0]),
              'S2' : lambda uq,ip: uq[1] * np.conj(ip[1]),
              'S0' : lambda uq,ip: uq[2] * np.conj(ip[2]),
              'SA' : lambda uq,ip: (vA @ uq) * np.conj(vA @ ip),
              'SB' : lambda uq,ip: (vB @ uq) * np.conj(vB @ ip),
              'SC' : lambda uq,ip: (vC @ uq) * np.conj(vC @ ip),
              'SAB' : lambda uq,ip: (vAB @ uq) * np.conj(vAB @ ip),
              'SBC' : lambda uq,ip: (vBC @ uq) * np.conj(vBC @ ip),
              'SCA' : lambda uq,ip: (vCA @ uq) * np.conj(vCA @ ip),
              'SABC' : lambda uq,ip: (Ms2f @ uq) * np.conj(Ms2f @ ip),
              'S' : lambda uq,ip: np.sum((Ms2f @ uq) * np.conj(Ms2f @ ip)),
              'SAB_BC_CA' : lambda uq,ip: (Ms2ff @ uq) * np.conj(Ms2ff @ ip)
              })

mform1=dict({'' : lambda res,parname: res,
              'R' : lambda res,parname: np.real(res),
              'X' : lambda res,parname: np.imag(res),
              'M' : lambda res,parname: np.abs(res),
              '<f' : lambda res,parname:  r2d*np.angle(res),
              'R+jX' : lambda res,parname: "{0:<4} = {1:>8.1f} + {2:>8.1f}j".format(parname, np.real(res),np.imag(res)),
              'M<f' : lambda res,parname: "{0:<4} = {1:>8.1f} ∠ {2:>6.1f}".format(parname, np.abs(res),r2d*np.angle(res))
              })

mform3=dict({'' : lambda res,parname: res,
              'R' : lambda res,parname: np.real(res),
              'X' : lambda res,parname: np.imag(res),
              'M' : lambda res,parname: np.abs(res),
              '<f' : lambda res,parname:  r2d*np.angle(res),
              'R+jX' : lambda res,parname: "{0:<4} = [{1:>8.1f} + {2:>8.1f}j, {3:>8.1f} + {4:>8.1f}j, {5:>8.1f} + {6:>8.1f}j]".format(parname, np.real(res[0]), np.imag(res[0]), np.real(res[1]), np.imag(res[1]), np.real(res[2]), np.imag(res[2])),
              'M<f' : lambda res,parname: "{0:<4} = [{1:>8.1f} ∠ {2:>6.1f}, {3:>8.1f} ∠ {4:>6.1f}, {5:>8.1f} ∠ {6:>6.1f}]".format(parname, np.abs(res[0]), r2d*np.angle(res[0]), np.abs(res[1]), r2d*np.angle(res[1]), np.abs(res[2]), r2d*np.angle(res[2]))
              })


def StrU(u120):
    strUABC = "| UA  = {0:>7.0f} ∠ {1:>6.1f} | UB  = {2:>7.0f} ∠ {3:>6.1f} | UC  = {4:>7.0f} ∠ {5:>6.1f} |\n"
    strU120 = "| U1  = {0:>7.0f} ∠ {1:>6.1f} | U2  = {2:>7.0f} ∠ {3:>6.1f} | 3U0 = {4:>7.0f} ∠ {5:>6.1f} |\n"
    strUAB_BC_CA = "| UAB = {0:>7.0f} ∠ {1:>6.1f} | UBC = {2:>7.0f} ∠ {3:>6.1f} | UCA = {4:>7.0f} ∠ {5:>6.1f} |\n"
    u1,u2,u0 = u120
    uA,uB,uC = Ms2f @ u120
    uAB,uBC,uCA = Ms2ff @ u120
    resstr = []
    resstr.append(strUABC.format(np.abs(uA),r2d*np.angle(uA),np.abs(uB),r2d*np.angle(uB),np.abs(uC),r2d*np.angle(uC)))
    resstr.append(strU120.format(np.abs(u1),r2d*np.angle(u1),np.abs(u2),r2d*np.angle(u2),np.abs(3*u0),r2d*np.angle(u0)))
    resstr.append(strUAB_BC_CA.format(np.abs(uAB),r2d*np.angle(uAB),np.abs(uBC),r2d*np.angle(uBC),np.abs(uCA),r2d*np.angle(uCA)))
    return ''.join(resstr)

def StrI(i120, Iff=1):
    strIABC = "| IA  = {0:>7.0f} ∠ {1:>6.1f} | IB  = {2:>7.0f} ∠ {3:>6.1f} | IC  = {4:>7.0f} ∠ {5:>6.1f} |\n"
    strI120 = "| I1  = {0:>7.0f} ∠ {1:>6.1f} | I2  = {2:>7.0f} ∠ {3:>6.1f} | 3I0 = {4:>7.0f} ∠ {5:>6.1f} |\n"
    i1,i2,i0 = i120
    iA,iB,iC = Ms2f @ i120
    resstr = []
    resstr.append(strIABC.format(np.abs(iA),r2d*np.angle(iA),np.abs(iB),r2d*np.angle(iB),np.abs(iC),r2d*np.angle(iC)))
    resstr.append(strI120.format(np.abs(i1),r2d*np.angle(i1),np.abs(i2),r2d*np.angle(i2),np.abs(3*i0),r2d*np.angle(i0)))
    if Iff:
        strIAB_BC_CA = "| IAB = {0:>7.0f} ∠ {1:>6.1f} | IBC = {2:>7.0f} ∠ {3:>6.1f} | ICA = {4:>7.0f} ∠ {5:>6.1f} |\n"
        iAB,iBC,iCA = Ms2ff @ i120
        resstr.append(strIAB_BC_CA.format(np.abs(iAB),r2d*np.angle(iAB),np.abs(iBC),r2d*np.angle(iBC),np.abs(iCA),r2d*np.angle(iCA)))
    return ''.join(resstr)


'''

 #Функции, добавленные Артуром Клементом


#Функция создает узел промежуточного КЗ, создает линии для жтого участка, удаляет общую линию(в работе). Возвращает список из Двух линий и узла

def kz_q(mdl, line, percentage_of_line=0.5, show_G=True):
    q_x = min(line.q1.x, line.q2.x) + abs(line.q1.x - line.q2.x)*percentage_of_line
    q_y = min(line.q1.y, line.q2.y) + abs(line.q1.y - line.q2.y)*percentage_of_line

    sub_mdl = mdl

    KZ_q = mrtkz.Q(sub_mdl,'KZ', x=q_x, y=q_y) # создаем узел КЗ
    Zq1=tuple(percentage_of_line * elem for elem in Line2.Z) # рассчитываем сопротивление участка q1-кз
    q1_kz_line = mrtkz.P(sub_mdl,'q1-kz',line.q1,KZ_q,Zq1) # вводим участок q1-кз

    Zq2=tuple((1-percentage_of_line) * elem for elem in line.Z) # рассчитываем сопротивление участка q2-кз
    kz_q2_line = mrtkz.P(sub_mdl,'kz-q2',KZ_q,line.q2,Zq2) # вводим участок q2-кз
    sub_mdl = p_del(sub_mdl, del_p_name=line.name, show_G=show_G)
        
    return sub_mdl




#Функция создает подрежим в котором удален узел "del_q_name" по имени узла q.name. Также удаляются ветви, связанные с этим узлом

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
    submdl.Calc()
    if show_G:
        print_G(submdl)
    return submdl




#Функция удаляет ветвь и ее узыл, если они тупиковые

def p_del(mdl, del_p_name='',q1_name='', q2_name='', show_G=True):
    if (del_p_name=='') and (q1_name=='' or q2_name==''):
        print('Ведите название линии в del_p_name или названия узлов в q1_name и q2_name')
        return
    if (del_p_name!='') and (q1_name!='' or q2_name!=''):
        print('Ведите либо название линии в del_p_name, либо названия узлов в q1_name и q2_name. Не одновременно.')
        return
    submdl=mrtkz.Model() # создаем подрежим
    submdl.Clear()
    submdl=mrtkz.Model()
    q_list = []

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
        if p.name == del_p_name or (q1_p_name == q1_name and  q2_p_name == q2_name) or (q1_p_name == q2_name and  q2_p_name == q1_name):
            print('Удаляем ветвь', p.name)
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
    if show_G:
        print_G(submdl)
    return submdl



#Визуализация участка энергосистемы (пока только узлы, линии и нулевые узлы)

def print_G(mdl):
    pos = nx.get_node_attributes(mdl.G, 'pos')
    nx.draw(mdl.G, pos, with_labels=True, node_color='lightblue', node_size=500, font_size=10, font_weight='bold')
    edge_labels = nx.get_edge_attributes(mdl.G, 'weight')
    nx.draw_networkx_edge_labels(mdl.G, pos, edge_labels=edge_labels)

    plt.title("Участок энергосистемы")
    plt.axis('off')
    plt.show()
    '''