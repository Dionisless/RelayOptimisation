import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog, filedialog
import threading
import time
import queue
import sys
import io
import math
# Если используете matplotlib для графиков
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

import kar_mrtkz as ktkz
import mrtkz3 as mrtkz
import kar_analyse as kanl
import optuna  

import kar_optimisation_pypeline as kar_opt


# Функции, предоставленные вами

def show_bad_results(mdl, submdl_dict):
    prot_work = kanl.analyze_relay_protections(mdl, submdl_dict, log=False, range_prot_analyse=False, print_G=False)
    i = 0
    bad_sm_dict = {}
    for work_id in prot_work:
        work = prot_work[work_id]
        if work_id == -666:
            i += 1
            sm = submdl_dict[work['submdl_id']]
            bad_sm_dict[i] = {'type': 'Неоткл КЗ', 'id': sm['id'], 'line_kz': sm['line_kz'], 'kz_type': sm['kz_type'], 'percent': sm['percent'], 'p_off': sm['p_off']}
        elif not (work['line'] in ['q1-kz', 'kz-q2', work['line_kz'], 0, '0']):
            i += 1
            sm = submdl_dict[work['submdl_id']]
            bad_sm_dict[i] = {'type': 'Неселект', 'id': sm['id'], 'line_kz': sm['line_kz'], 'kz_type': sm['kz_type'], 'percent': sm['percent'], 'p_off': sm['p_off']}
    return bad_sm_dict, prot_work

def make_G_list(mdl, submdl_dict, sm_id, prot_work):
    submdl = kanl.to_submdl(mdl, submdl_dict[sm_id])
    smdl_dict = {}
    smdl_dict[0] = {'t': 'До КЗ', 'sm': submdl}
    temp_sm_work_dict = {}

    # Сбор всех срабатываний для конкретного подрежима
    for work_id in prot_work:
        work = prot_work[work_id]
        if work['submdl_id'] == sm_id and work['id'] != -666:
            t = work['t']
            if t not in temp_sm_work_dict:
                temp_sm_work_dict[t] = []  # Создаем список событий для данного времени
            temp_sm_work_dict[t].append(work['line'])  # Записываем линию, отключенную в это время

    # Сортировка событий по времени
    sorted_times = sorted(temp_sm_work_dict.keys())

    # Обработка срабатываний и обновление сети
    submdl_copy = submdl  # Копируем подрежим, чтобы не модифицировать исходный
    for k, t in enumerate(sorted_times):
        lines_to_off = temp_sm_work_dict[t]
        print(t, lines_to_off)
        submdl_copy = ktkz.p_del(submdl_copy, del_p_name=lines_to_off, show_G=False, show_par=False)  # Отключение линии
        smdl_dict[k + 1] = {'t': t, 'sm': submdl_copy}  # Записываем состояние сети после отключений

    return smdl_dict  # Словарь, содержащий времена и модели с отключениями


class PowerGridOptimizationApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Программа оптимизации уставок (прототип)")
        self.geometry("1000x650")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill="both")

        self.grid_page = ttk.Frame(self.notebook)
        self.subregimes_page = ttk.Frame(self.notebook)
        self.optimization_page = ttk.Frame(self.notebook)
        self.analysis_page = ttk.Frame(self.notebook)
        
        self.notebook.add(self.grid_page, text="Сеть")
        self.notebook.add(self.subregimes_page, text="Подрежимы")
        self.notebook.add(self.optimization_page, text="Оптимизация")
        self.notebook.add(self.analysis_page, text="Анализ")
        
        self.mdl = mrtkz.Model()
        self.submdl_dict = {}
        
        self.setup_analysis_page()
        self.setup_grid_page()
        self.setup_subregimes_page()
        self.setup_optimization_page()

        self.bind("<Configure>", self.on_resize)
        # Добавляем обработчик для изменения вкладок
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    ###### Страница сети ######
    def setup_grid_page(self):
        '''
        # Таблица подрежимов
        table_frame = ttk.Frame(upper_left_frame)
        table_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        columns = ("Type", "ID", "Line_KZ", "KZ_Type", "Percent", "P_off")
        self.bad_modes_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

        for col in columns:
            self.bad_modes_tree.heading(col, text=col)
            self.bad_modes_tree.column(col, width=80, anchor='center')

        self.bad_modes_tree.pack(fill=tk.BOTH, expand=True)

        self.bad_modes_tree.bind('<<TreeviewSelect>>', self.on_bad_mode_select)

        '''
        left_frame = ttk.Frame(self.grid_page, width=600)
        left_frame.pack(side="left", fill="both", expand=False)
        left_frame.pack_propagate(False)

        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(side="top", fill="x", padx=5, pady=5)

        ttk.Button(btn_frame, text="Загрузка из файла", command=self.load_from_file).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Сохранение в файл", command=self.save_to_file).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Очистка сети", command=self.clear_network).pack(side="left", padx=5)

        self.object_var = tk.StringVar(value="Узлы")
        object_menu = ttk.Combobox(left_frame, textvariable=self.object_var, values=["Узлы", "Линии"])
        object_menu.pack(side="top", fill="x", padx=5, pady=5)
        object_menu.bind("<<ComboboxSelected>>", self.update_table)

        table_frame = ttk.Frame(left_frame)
        #table_frame.pack(side="top", fill="both", expand=True, padx=5, pady=5)
        table_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.tree = ttk.Treeview(table_frame)
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(side="bottom", fill="x", padx=5, pady=5)
        ttk.Button(btn_frame, text="Добавить", command=self.add_object).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Удалить", command=self.delete_object).pack(side="left", padx=5)
        
        # Добавляем кнопку "тестовая модель"
        ttk.Button(btn_frame, text="Тестовая модель", command=self.load_test_model).pack(side="left", padx=5)

        right_frame = ttk.Frame(self.grid_page, width=600)
        right_frame.pack(side="right", fill="both", expand=True)

        self.canvas = tk.Canvas(right_frame, bg="white")
        self.canvas.pack(fill="both", expand=True)

        self.update_table()
        self.update_visualization()

    def update_visualization(self):
        self.canvas.delete("all")
        
        self.mdl.Calc()  # Выполняем расчет параметров модели
        G = self.mdl.G  # Граф, представляющий модель
        
        if not G.nodes:
            print("No nodes in graph.")
            return
    
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        node_positions = {node: data['pos'] for node, data in G.nodes(data=True) if 'pos' in data}
        if not node_positions:
            print("No node positions available.")
            return
    
        # Масштабирование и преобразование координат
        min_x = min(x for x, y in node_positions.values())
        max_x = max(x for x, y in node_positions.values())
        min_y = min(y for x, y in node_positions.values())
        max_y = max(y for x, y in node_positions.values())
        
        padding = 40
        usable_width = max(1, canvas_width - 2 * padding)
        usable_height = max(1, canvas_height - 2 * padding)
        
        scale_x = usable_width / max(1, max_x - min_x)
        scale_y = usable_height / max(1, max_y - min_y)
        scale = min(scale_x, scale_y)
        
        def to_canvas_coords(x, y):
            canvas_x = padding + (x - min_x) * scale
            canvas_y = canvas_height - (padding + (y - min_y) * scale)
            return int(canvas_x), int(canvas_y)
    
        # Определение цветов узлов
        node_colors = {}
        for n in self.mdl.bn:
            kz_name = n.qp.name
            node_colors[kz_name] = 'red'
        
        for q in self.mdl.bp:
            if q.E[0] != 0:
                gen_name = q.name + '_0'
                node_colors[gen_name] = 'darkblue'
    
        # Отрисовка рёбер и их меток
        for p in self.mdl.bp:
            q1_name = p.q1.name if p.q1 != 0 else p.name + '_0'
            q2_name = p.q2.name if p.q2 != 0 else p.name + '_0'
            
            start = to_canvas_coords(*node_positions[q1_name])
            end = to_canvas_coords(*node_positions[q2_name])

            self.canvas.create_line(start[0], start[1], end[0], end[1], fill="blue", width=2, arrow=tk.LAST)
            '''
            mid_x = (start[0] + end[0]) / 2
            mid_y = (start[1] + end[1]) / 2
            self.canvas.create_text(mid_x, mid_y, text={p.name}, font=("Arial", 8))
            '''
            # Вычисление угла наклона линии для размещения текста
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            angle = math.atan2(dy, dx)
            text_angle = math.degrees(angle)
        
            # Корректировка угла для правильной ориентации текста
            if -90 <= text_angle <= 90:
                text_angle = -text_angle
            else:
                text_angle = 180 - text_angle
        
            mid_x = (start[0] + end[0]) / 2
            mid_y = (start[1] + end[1]) / 2
            
            # Создаем текст с правильным углом наклона
            text = self.canvas.create_text(mid_x, mid_y, text=p.name, font=("Arial", 8), angle=text_angle)
            
            # Получаем границы текста
            bbox = self.canvas.bbox(text)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Смещаем текст перпендикулярно линии
            offset = -10  # Расстояние смещения от линии
            perpendicular_angle = angle + math.pi/2
            offset_x = offset * math.cos(perpendicular_angle)
            offset_y = offset * math.sin(perpendicular_angle)
            
            self.canvas.move(text, offset_x, offset_y)



        
    
        # Отрисовка взаимной индукции
        for m in self.mdl.bm:
            line1, line2 = m.p1, m.p2
            x11, y11 = to_canvas_coords(*(node_positions[line1.q1.name] if line1.q1 != 0 else (0, 0)))
            x12, y12 = to_canvas_coords(*(node_positions[line1.q2.name] if line1.q2 != 0 else (0, 0)))
            x21, y21 = to_canvas_coords(*(node_positions[line2.q1.name] if line2.q1 != 0 else (0, 0)))
            x22, y22 = to_canvas_coords(*(node_positions[line2.q2.name] if line2.q2 != 0 else (0, 0)))
    
            mid1_x, mid1_y = (x11 + x12) / 2, (y11 + y12) / 2
            mid2_x, mid2_y = (x21 + x22) / 2, (y21 + y22) / 2
            self.canvas.create_line(mid1_x, mid1_y, mid2_x, mid2_y, fill="gray", dash=(2, 2))
    
        # Отрисовка узлов
        for node, (x, y) in node_positions.items():
            canvas_x, canvas_y = to_canvas_coords(x, y)
            color = node_colors.get(node, 'lightblue')
            self.canvas.create_oval(canvas_x-5, canvas_y-5, canvas_x+5, canvas_y+5, fill=color, outline="black")
            self.canvas.create_text(canvas_x, canvas_y-15, text=str(node), font=("Arial", 10, "bold"))
    
        self.canvas.update()
            #print(f"Canvas size: {canvas_width}x{canvas_height}")
            #print(f"Number of nodes: {len(node_positions)}")
            #print(f"Number of edges: {len(G.edges())}")

    def load_from_file(self):
        filename = filedialog.askopenfilename(filetypes=[("All Files", "*.*")])
        if filename:
            # Здесь должна быть логика загрузки из файла
            pass

    def save_to_file(self):
        filename = filedialog.asksaveasfilename(filetypes=[("All Files", "*.*")])
        if filename:
            # Здесь должна быть логика сохранения в файл
            pass

    def clear_network(self):
        self.mdl.Clear()
        self.update_table()
        self.update_visualization()
        self.update_subregimes_visualization()

    def update_table(self, event=None):

        
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if self.object_var.get() == "Узлы":
            self.tree["columns"] = ["Название", "X", "Y", "Y1", "Y2", "Y0", "J1", "J2", "J0", "Описание"]
            self.tree.heading("Название", text="Название")
            self.tree.heading("X", text="X")
            self.tree.heading("Y", text="Y")
            self.tree.heading("Y1", text="Y1")
            self.tree.heading("Y2", text="Y2")
            self.tree.heading("Y0", text="Y0")
            self.tree.heading("J1", text="J1")
            self.tree.heading("J2", text="J2")
            self.tree.heading("J0", text="J0")
            self.tree.heading("Описание", text="Описание")

            # Ограничиваем ширину столбцов
            self.tree.column("Название", width=100, minwidth=50)
            self.tree.column("X", width=50, minwidth=50)
            self.tree.column("Y", width=50, minwidth=50)
            self.tree.column("Y1", width=50, minwidth=50)
            self.tree.column("Y2", width=50, minwidth=50)
            self.tree.column("Y0", width=50, minwidth=50)
            self.tree.column("J1", width=50, minwidth=50)
            self.tree.column("J2", width=50, minwidth=50)
            self.tree.column("J0", width=50, minwidth=50)
            self.tree.column("Описание", width=200, minwidth=100)
            
            for q in self.mdl.bq:
                self.tree.insert("", "end", values=(q.name, q.x, q.y, 
                                                    complex(q.Y[0]), complex(q.Y[1]), complex(q.Y[2]),
                                                    complex(q.J[0]), complex(q.J[1]), complex(q.J[2]),
                                                    q.desc))
        else:
            self.tree["columns"] = ["Название", "От узла", "К узлу", "Z1", "Z2", "Z0", "E1", "E2", "E0", "B1", "B2", "B0", "Ktrans", "GrT", "Описание"]
            self.tree.heading("Название", text="Название")
            self.tree.heading("От узла", text="От узла")
            self.tree.heading("К узлу", text="К узлу")
            self.tree.heading("Z1", text="Z1")
            self.tree.heading("Z2", text="Z2")
            self.tree.heading("Z0", text="Z0")
            self.tree.heading("E1", text="E1")
            self.tree.heading("E2", text="E2")
            self.tree.heading("E0", text="E0")
            self.tree.heading("B1", text="B1")
            self.tree.heading("B2", text="B2")
            self.tree.heading("B0", text="B0")
            self.tree.heading("Ktrans", text="Ktrans")
            self.tree.heading("GrT", text="GrT")
            self.tree.heading("Описание", text="Описание")

            # Ограничиваем ширину столбцов
            self.tree.column("Название", width=100, minwidth=50)
            self.tree.column("От узла", width=80, minwidth=50)
            self.tree.column("К узлу", width=80, minwidth=50)
            self.tree.column("Z1", width=80, minwidth=50)
            self.tree.column("Z2", width=80, minwidth=50)
            self.tree.column("Z0", width=80, minwidth=50)
            self.tree.column("E1", width=80, minwidth=50)
            self.tree.column("E2", width=80, minwidth=50)
            self.tree.column("E0", width=80, minwidth=50)
            self.tree.column("B1", width=80, minwidth=50)
            self.tree.column("B2", width=80, minwidth=50)
            self.tree.column("B0", width=80, minwidth=50)
            self.tree.column("Ktrans", width=80, minwidth=50)
            self.tree.column("GrT", width=80, minwidth=50)
            self.tree.column("Описание", width=200, minwidth=100)

            for p in self.mdl.bp:
                from_node = p.q1.name if p.q1 else "0"
                to_node = p.q2.name if p.q2 else "0"
                E = getattr(p, 'E', (None, None, None))
                B = getattr(p, 'B', (None, None, None))
                T = getattr(p, 'T', (None, None))
                self.tree.insert("", "end", values=(p.name, from_node, to_node,
                                                    complex(p.Z[0]), complex(p.Z[1]), complex(p.Z[2]),
                                                    complex(E[0]) if E[0] else "", complex(E[1]) if E[1] else "", complex(E[2]) if E[2] else "",
                                                    complex(B[0]) if B[0] else "", complex(B[1]) if B[1] else "", complex(B[2]) if B[2] else "",
                                                    T[0] if T else "", T[1] if T else "",
                                                    p.desc))

    def add_object(self):
        if self.object_var.get() == "Узлы":
            name = simpledialog.askstring("Добавить узел", "Введите название узла:")
            if not name:
                return
    
            x = simpledialog.askfloat("Добавить узел", "Введите координату X (по умолчанию 0):", initialvalue=0) or 0
            y = simpledialog.askfloat("Добавить узел", "Введите координату Y (по умолчанию 0):", initialvalue=0) or 0
            
            Y = self.ask_complex_tuple("Введите проводимость Y (Y1,Y2,Y0) в См", (0,0,0))
            J = self.ask_complex_tuple("Введите источник тока J (J1,J2,J0) в А", (0,0,0))
            desc = simpledialog.askstring("Добавить узел", "Введите описание (необязательно):") or ''
    
            mrtkz.Q(self.mdl, name, Y=Y, J=J, desc=desc, x=x, y=y)
    
        else:  # Линии
            name = simpledialog.askstring("Добавить линию", "Введите название линии:")
            if not name:
                return
    
            from_node = simpledialog.askstring("Добавить линию", "Введите название начального узла:")
            to_node = simpledialog.askstring("Добавить линию", "Введите название конечного узла:")
            
            q1 = next((q for q in self.mdl.bq if q.name == from_node), None)
            q2 = next((q for q in self.mdl.bq if q.name == to_node), None)
            
            if not (q1 and q2):
                tk.messagebox.showerror("Ошибка", "Один или оба узла не найдены")
                return
    
            Z = self.ask_complex_tuple("Введите сопротивление Z (Z1,Z2,Z0) в Ом", (10j, 10j, 30j))
            E = self.ask_complex_tuple("Введите ЭДС E (E1,E2,E0) в Вольтах (необязательно)", None)
            B = self.ask_complex_tuple("Введите емкостную проводимость B (B1,B2,B0) в См (необязательно)", None)
            
            T = None
            if tk.messagebox.askyesno("Трансформатор", "Это трансформаторная ветвь?"):
                Ktrans = simpledialog.askfloat("Трансформатор", "Введите коэффициент трансформации:")
                GrT = simpledialog.askinteger("Трансформатор", "Введите группу обмоток (0-11):", minvalue=0, maxvalue=11)
                if Ktrans is not None and GrT is not None:
                    T = (Ktrans, GrT)
    
            desc = simpledialog.askstring("Добавить линию", "Введите описание (необязательно):") or ''
    
            mrtkz.P(self.mdl, name, q1, q2, Z, E=E, B=B, T=T, desc=desc)
    
        self.update_table()
        self.update_visualization()
        self.update_subregimes_visualization()
    
    def ask_complex_tuple(self, prompt, default=None):
        result = []
        for i in range(3):
            while True:
                value = simpledialog.askstring(prompt, f"Введите {i+1}-е значение (действительная и мнимая части через пробел):")
                if not value and default:
                    return default
                if not value:
                    return None
                try:
                    real, imag = map(float, value.split())
                    result.append(complex(real, imag))
                    break
                except ValueError:
                    tk.messagebox.showerror("Ошибка", "Неверный формат. Введите два числа, разделенных пробелом.")
        return tuple(result)

    def delete_object(self):
        selected_items = self.tree.selection()
        if not selected_items:
            tk.messagebox.showerror("Ошибка", "Выберите объект для удаления")
            return

        selected_item = selected_items[0]
        values = self.tree.item(selected_item)['values']
        
        if self.object_var.get() == "Узлы":
            self.mdl = ktkz.q_del(self.mdl, values[0])  # Удаление узла
        else:
            self.mdl = ktkz.p_del(self.mdl, values[0])  # Удаление линии

        self.update_table()
        self.update_visualization()
        self.update_subregimes_visualization()


    def load_test_model(self):
        self.mdl = ktkz.base_model()
        self.update_table()
        self.update_idletasks()  # Обновляем GUI
        self.update_visualization()
        self.update_subregimes_visualization()
        print("Test model loaded")
        print(f"Number of nodes: {len(self.mdl.bq)}")
        print(f"Number of branches: {len(self.mdl.bp)}")
    def on_resize(self, event):
        if event.widget == self:
            self.update_visualization()
            self.update_subregimes_visualization()


    ###### Страница подрежимов ######
    def setup_subregimes_page(self):
        # Фрейм для ввода
        input_frame = ttk.Frame(self.subregimes_page, padding="10")
        input_frame.pack(fill=tk.BOTH, expand=True)

        # Поле ввода с автопереносом текста
        self.input_entry = scrolledtext.ScrolledText(input_frame, wrap=tk.WORD, height=4)
        #self.input_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        self.input_entry.pack(side=tk.LEFT, fill="x", expand=True, padx=5, pady=5)
        # Добавляем значение по умолчанию
        default_text = "(ПОЯС[1]+ИНДУКЦ)*ТИПКЗ[A0]*ЛИНИИКЗ[ВСЕ]*ШАГ[0.999]*ПЕРЕБОР[1]"
        self.input_entry.insert(tk.INSERT, default_text)
        #object_menu = ttk.Combobox(left_frame, textvariable=self.object_var, values=["Узлы", "Линии"])
        #object_menu.pack(side="top", fill="x", padx=5, pady=5)
        # Кнопка выполнения
        execute_button = ttk.Button(input_frame, text="Выполнить", command=self.execute_calculation)
        execute_button.pack(side=tk.LEFT)

        # Фрейм для кнопок функций
        buttons_frame = ttk.Frame(self.subregimes_page, padding="10")
        buttons_frame.pack(fill=tk.X)
        buttons_frame2 = ttk.Frame(self.subregimes_page, padding="10")
        buttons_frame2.pack(fill=tk.X)

        # Кнопки функций
        functions_1 = [
            ("ПОЯС[int]", "ПОЯС[]"),
            ("ИНДУКЦ", "ИНДУКЦ"),
            ("ОБЪЕКТЫ[line1,line2]", "ОБЪЕКТЫ[]"),
            ("МАКСТОК[int]", "МАКСТОК[]"),
        ]
        functions_2 = [
            ("ЛИНИИКЗ[line1,line2]", "ЛИНИИКЗ[]"),
            ("ПЕРЕБОР[int]", "ПЕРЕБОР[]"),
            ("ТИПКЗ[ABC,A0]", "ТИПКЗ[]"),
            ("ШАГ[0.2]", "ШАГ[]")
        ]
        for text, template in functions_1:
            button = ttk.Button(buttons_frame, text=text, command=lambda t=template: self.add_function(t))
            button.pack(side=tk.LEFT, padx=5)
        for text, template in functions_2:
            button = ttk.Button(buttons_frame2, text=text, command=lambda t=template: self.add_function(t))
            button.pack(side=tk.LEFT, padx=5)

        # Фрейм для счетчика и кнопки уточнения
        counter_frame = ttk.Frame(self.subregimes_page, padding="10")
        counter_frame.pack(fill=tk.X)

        # Метка для вывода количества подрежимов и времени расчета
        self.counter_label = ttk.Label(counter_frame, text="Подрежимов: 0, Расчетное время: 0 с.")
        self.counter_label.pack(side=tk.LEFT, padx=5)

        # Кнопка для уточнения времени расчета
        self.refine_button = ttk.Button(counter_frame, text="Уточнить расчет", command=self.refine_calculation)
        self.refine_button.pack(side=tk.LEFT, padx=5)



        # Фреймы для разделения результатов и визуализации на странице подрежимов
        result_and_visualization_frame = ttk.Frame(self.subregimes_page)
        result_and_visualization_frame.pack(fill=tk.BOTH, expand=True)
    
        result_frame = ttk.Frame(result_and_visualization_frame)
        result_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
        visualization_frame = ttk.Frame(result_and_visualization_frame)
        visualization_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
    
        # Область вывода результатов
        self.result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD)
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
        # Область для визуализации
        self.submdl_canvas = tk.Canvas(visualization_frame, bg="white")
        self.submdl_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.update_subregimes_visualization()

    def add_function(self, template):
        current_text = self.input_entry.get("1.0", tk.END).strip()
        if current_text and not current_text.endswith(("*", "+", "(")):
            current_text += "*"
        self.input_entry.delete("1.0", tk.END)
        self.input_entry.insert("1.0", current_text + template)

    def execute_calculation(self):
        task_str = str(self.input_entry.get("1.0", tk.END)).strip()
        print(task_str)
        try:
            self.result_text.delete("1.0", tk.END)  # Очистка области вывода результатов
            self.submdl_dict = {}  # Инициализация нового пустого словаря
            self.submdl_dict = kanl.submdl_calc_main(self.mdl, task_str, self.submdl_dict)
            self.display_result(self.submdl_dict)
            self.update_counter(len(self.submdl_dict))
        except Exception as e:
            self.display_result(f"Ошибка: {str(e)}")

    def refine_calculation(self):
        try:
            start_time = time.time()
            #self.submdl_dict = self.result_text.get("1.0", tk.END).strip()
            #self.submdl_dict = eval(self.submdl_dict) if isinstance(self.submdl_dict, str) else self.submdl_dict
            kanl.ML_func(self.mdl, self.submdl_dict)
            refined_time = time.time() - start_time
            print(refined_time)
            self.counter_label.config(text=f"Подрежимов: {len(self.submdl_dict)}, Уточненное время: {refined_time:.2f} с.")
        except Exception as e:
            self.display_result(f"Ошибка: {str(e)}")

    def update_counter(self, num_subregimes):
        approximate_time = self.mdl.np * num_subregimes * 0.0045
        self.counter_label.config(text=f"Подрежимов: {num_subregimes}, Расчетное время: {approximate_time:.2f} с.")

    def display_result(self, result):
        self.result_text.delete("1.0", tk.END)
        if isinstance(result, dict):
            for key, value in result.items():
                self.result_text.insert(tk.END, f"Подрежим {key}:\n")
                for k, v in value.items():
                    self.result_text.insert(tk.END, f"  {k}: {v}\n")
                self.result_text.insert(tk.END, "\n")
        else:
            self.result_text.insert(tk.END, str(result))

    def on_resize(self, event):
        # Метод для обработки события изменения размера окна
        if event.widget == self:
            self.update_visualization()
            self.update_subregimes_visualization()
    def on_tab_changed(self, event):
        selected_tab = event.widget.select()
        tab_text = event.widget.tab(selected_tab, "text")
        if tab_text == "Подрежимы":
            self.update_subregimes_visualization()
        elif tab_text =="Анализ":
            self.on_recalculate()
            
    def update_subregimes_visualization(self):
        self.submdl_canvas.delete("all")
        G = self.mdl.G
        #print("mdl_data", self.mdl.np, self.mdl.G)
        if not G.nodes:
            return
    
        canvas_width = self.submdl_canvas.winfo_width()
        canvas_height = self.submdl_canvas.winfo_height()
        node_positions = {node: data['pos'] for node, data in G.nodes(data=True) if 'pos' in data}
        if not node_positions:
            return
    
        # Аналогично тому, как вы масштабируете координаты на первой странице
        min_x = min(x for x, y in node_positions.values())
        max_x = max(x for x, y in node_positions.values())
        min_y = min(y for x, y in node_positions.values())
        max_y = max(y for x, y in node_positions.values())
    
        padding = 40
        usable_width = max(1, canvas_width - 2 * padding)
        usable_height = max(1, canvas_height - 2 * padding)
    
        scale_x = usable_width / max(1, max_x - min_x)
        scale_y = usable_height / max(1, max_y - min_y)
        scale = min(scale_x, scale_y)
    
        def to_canvas_coords(x, y):
            canvas_x = padding + (x - min_x) * scale
            canvas_y = canvas_height - (padding + (y - min_y) * scale)
            return int(canvas_x), int(canvas_y)
    
        for edge in G.edges():
            if edge[0] in node_positions and edge[1] in node_positions:
                start = to_canvas_coords(*node_positions[edge[0]])
                end = to_canvas_coords(*node_positions[edge[1]])
                self.submdl_canvas.create_line(start[0], start[1], end[0], end[1], fill="blue", width=2)
    
        for node, (x, y) in node_positions.items():
            canvas_x, canvas_y = to_canvas_coords(x, y)
            self.submdl_canvas.create_oval(canvas_x-5, canvas_y-5, canvas_x+5, canvas_y+5, fill="red", outline="black")
            self.submdl_canvas.create_text(canvas_x, canvas_y-15, text=str(node), font=("Arial", 10, "bold"))


    ###### Страница оптимизации ######
    def setup_optimization_page(self):
        # Фреймы для организации элементов
        parameters_frame = ttk.Frame(self.optimization_page, padding="10")
        parameters_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        output_frame = ttk.Frame(self.optimization_page, padding="10")
        output_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Переменные для параметров оптимизации с значениями по умолчанию
        self.no_off_var = tk.DoubleVar(value=10)
        self.off_var = tk.DoubleVar(value=0)
        self.non_select_var = tk.DoubleVar(value=1)
        self.k_loss_time_var = tk.DoubleVar(value=5)
        self.k_loss_k_ch_var = tk.DoubleVar(value=0)

        self.dist_prot_anl_var = tk.BooleanVar(value=False)
        self.no_off_dist_var = tk.DoubleVar(value=5)
        self.off_dist_var = tk.DoubleVar(value=0)
        self.non_select_dist_var = tk.DoubleVar(value=0.3)
        self.k_loss_time_dist_var = tk.DoubleVar(value=0.2)
        self.k_loss_k_ch_dist_var = tk.DoubleVar(value=0)

        self.k_ots_var = tk.DoubleVar(value=1.1)
        self.k_ch_var = tk.DoubleVar(value=0.9)

        self.n_iterations_var = tk.IntVar(value=200)
        self.n_stages_var = tk.IntVar(value=4)
        self.extended_log_var = tk.BooleanVar(value=True)

        # Фрейм для весовых коэффициентов ошибки
        weights_frame = ttk.LabelFrame(parameters_frame, text="Веса ошибки", padding="10")
        weights_frame.pack(fill=tk.X, expand=False)

        weight_params = [
            ("Неотключение КЗ", self.no_off_var),
            ("Отключение КЗ", self.off_var),
            ("Неселективное срабатывание", self.non_select_var),
            ("К*среднее время отключения", self.k_loss_time_var),
            ("К*среднее Кч", self.k_loss_k_ch_var),
        ]
        for i, (label_text, var) in enumerate(weight_params):
            ttk.Label(weights_frame, text=f"{label_text}:").grid(row=i, column=0, sticky=tk.W)
            ttk.Entry(weights_frame, textvariable=var).grid(row=i, column=1)
            
        # Фрейм для дальнего резервирования    
        dist_weights_frame = ttk.LabelFrame(parameters_frame, text="Веса ошибки дальнее резервирование", padding="10")
        dist_weights_frame.pack(fill=tk.X, expand=False)
        dist_weight_params = [ 
            ("Неотключение КЗ", self.no_off_dist_var),
            ("Отключение КЗ", self.off_dist_var),
            ("Неселективное срабатывание", self.non_select_dist_var),
            ("К*среднее время отключения", self.k_loss_time_dist_var),
            ("К*среднее Кч", self.k_loss_k_ch_dist_var),
        ]
        
        ttk.Checkbutton(dist_weights_frame, text="Анализировать дальнее резервирование", variable=self.dist_prot_anl_var).grid(row=0, column=0, columnspan=2, sticky=tk.W)
        for i, (label_text, var) in enumerate(dist_weight_params):
            ttk.Label(dist_weights_frame, text=f"{label_text}:").grid(row=i+1, column=0, sticky=tk.W)
            ttk.Entry(dist_weights_frame, textvariable=var).grid(row=i+1, column=1)
            
        
        # Фрейм для коэффициентов
        k_params_frame = ttk.LabelFrame(parameters_frame, text="Коэффициенты защит", padding="10")
        k_params_frame.pack(fill=tk.X, expand=False, pady=10)

        ttk.Label(k_params_frame, text="К отстройки:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(k_params_frame, textvariable=self.k_ots_var).grid(row=0, column=1)

        ttk.Label(k_params_frame, text="К чувствительности:").grid(row=1, column=0, sticky=tk.W)
        ttk.Entry(k_params_frame, textvariable=self.k_ch_var).grid(row=1, column=1)
        
        # Фрейм для других параметров
        other_params_frame = ttk.LabelFrame(parameters_frame, text="Другие параметры", padding="10")
        other_params_frame.pack(fill=tk.X, expand=False, pady=10)
        
        ttk.Label(other_params_frame, text="Количество итераций:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(other_params_frame, textvariable=self.n_iterations_var).grid(row=0, column=1)

        ttk.Label(other_params_frame, text="Количество ступеней защит:").grid(row=1, column=0, sticky=tk.W)
        ttk.Entry(other_params_frame, textvariable=self.n_stages_var).grid(row=1, column=1)

        ttk.Checkbutton(other_params_frame, text="Выводить результаты не оптимизационных функций", variable=self.extended_log_var).grid(row=2, column=0, columnspan=2, sticky=tk.W)

        # Кнопка для запуска оптимизации
        ttk.Button(parameters_frame, text="Начать оптимизацию", command=self.start_optimization).pack(pady=10)

        # Фрейм для графика
        graph_frame = ttk.Frame(output_frame)
        graph_frame.pack(fill=tk.BOTH, expand=True)

        # Фрейм для лога
        log_frame = ttk.Frame(output_frame)
        log_frame.pack(fill=tk.BOTH, expand=True)

        # Текстовое поле для лога
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Настройка графика
        self.figure = plt.Figure(figsize=(5, 4))
        self.ax_loss = self.figure.add_subplot(111)
        self.plot_canvas = FigureCanvasTkAgg(self.figure, master=graph_frame)
        self.plot_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Очереди для коммуникации между потоками
        self.log_queue = queue.Queue()
        self.loss_queue = queue.Queue()
        self.non_select_queue = queue.Queue()
        self.no_off_queue = queue.Queue()

        # Запуск обновления интерфейса
        self.update_ui()
    
    def start_optimization(self):
        # Получение параметров
        loss_params = {
            'no_off': self.no_off_var.get(),
            'off': self.off_var.get(),
            'non_select': self.non_select_var.get(),
            'k_loss_time': self.k_loss_time_var.get(),
            'k_loss_k_ch': self.k_loss_k_ch_var.get(),
            'no_off_dist': self.no_off_dist_var.get(),
            'off_dist': self.off_dist_var.get(),
            'non_select_dist': self.non_select_dist_var.get(),
            'k_loss_time_dist': self.k_loss_time_dist_var.get(),
            'k_loss_k_ch_dist': self.k_loss_k_ch_dist_var.get(),
        }


        k_ch = self.k_ch_var.get()
        k_ots = self.k_ots_var.get()
        
        n_iterations = self.n_iterations_var.get()
        n_stages = self.n_stages_var.get()
        extended_log = self.extended_log_var.get()

        # Очистка логов и графиков
        self.log_text.delete('1.0', tk.END)
        self.ax_loss.clear()
        self.plot_canvas.draw()

        # Запуск оптимизации в отдельном потоке
        threading.Thread(target=self.run_optimization, args=(loss_params, n_iterations, n_stages, extended_log, k_ch, k_ots)).start()
    

    def run_optimization(self, loss_params, n_iterations, n_stages, extended_log, k_ch, k_ots):
        mdl = self.mdl
        submdl_dict = self.submdl_dict
        
        def loss_callback(loss):
            self.loss_queue.put(loss)
            
        # Проверка наличия модели и словаря подрежимов
        if not mdl or not submdl_dict:
            self.log_queue.put("Ошибка: Модель или словарь подрежимов не загружены.")
            return
    
        # Перенаправление вывода в буфер
        old_stdout = sys.stdout
        sys.stdout = mystdout = io.StringIO()
    
        # Списки для графиков
        loss_list = []
    
        if extended_log:
            show_iterations = n_iterations + 9
        else:
            show_iterations = n_iterations + 4
    
        if extended_log:
            self.log_queue.put(f'Начата оптимизация {n_stages} ступеней защит сети.\nКоличество итераций целевой функции {n_iterations} с расчетным временем выполнения calculation_time')
        
        mdl = kar_opt.disable_prot(mdl)
    
        if extended_log:
            self.log_queue.put('\nВыводим все защиты (disable_prot)')
    
        submdl = kar_opt.calc_first_stage(mdl, submdl_dict, k_ots)
        if extended_log:
            self.log_queue.put('\nОтстраиваем первую ступень во всех подрежимах (calc_first_stage)')
            result = kanl.ML_func(submdl, submdl_dict, extended_result=True)
            self.log_queue.put(f'Общая ошибка: {result["loss"]}\nКоличество неселективных срабатываний: {result["non_select_count"]}\nКоличество селективных срабатываний: {result["select_count"]}\nДоля селективных срабатываний: {round(100-result["select_share"],1)}%\nКоличество неотключений: {result["no_off_count"]}\nСреднее время отключения: {round(result["mean_time"],2)} c')
            
        submdl = kar_opt.first_stage_update(submdl, submdl_dict, k_ots)
        if extended_log:
            self.log_queue.put('\nАнализируем срабатывания, отстраиваем первую ступень в упущенных подрежимах (first_stage_update)')
            result = kanl.ML_func(submdl, submdl_dict, extended_result=True)
            self.log_queue.put(f'Общая ошибка: {result["loss"]}\nКоличество неселективных срабатываний: {result["non_select_count"]}\nКоличество селективных срабатываний: {result["select_count"]}\nДоля селективных срабатываний: {round(100-result["select_share"])}%\nКоличество неотключений: {result["no_off_count"]}\nСреднее время отключения: {round(result["mean_time"],2)} c')
    
        submdl = kar_opt.calc_second_stage(submdl, submdl_dict, k_ch)
        if extended_log:
            self.log_queue.put('\nВыводим вторую ступень на чувствование тока КЗ на линии во всех подрежимах (calc_second_stage)')
            result = kanl.ML_func(submdl, submdl_dict, extended_result=True)
            self.log_queue.put(f'Общая ошибка: {result["loss"]}\nКоличество неселективных срабатываний: {result["non_select_count"]}\nКоличество селективных срабатываний: {result["select_count"]}\nДоля селективных срабатываний: {round(100-result["select_share"])}%\nКоличество неотключений: {result["no_off_count"]}\nСреднее время отключения: {round(result["mean_time"],2)} c')
    
        submdl = kar_opt.second_stage_update(submdl, submdl_dict, k_ch)
        if extended_log:
            self.log_queue.put('\nВыводим вторую ступень на чувствование тока КЗ в упущенных подрежимах (update_second_stage)')
            result = kanl.ML_func(submdl, submdl_dict, extended_result=True)
            self.log_queue.put(f'Общая ошибка: {result["loss"]}\nКоличество неселективных срабатываний: {result["non_select_count"]}\nКоличество селективных срабатываний: {result["select_count"]}\nДоля селективных срабатываний: {round(100-result["select_share"])}%\nКоличество неотключений: {result["no_off_count"]}\nСреднее время отключения: {round(result["mean_time"],2)} c')        
    
        # оптимизационная функция
        if n_stages == 2:
            optuna.logging.set_verbosity(optuna.logging.WARNING)
            kar_opt.optimize_protection_times(submdl, submdl_dict, n_trials=n_iterations, t_range=[1, 7], loss_params=loss_params)
            self.log_queue.put('\nОптимизируем времена срабатывания второй ступени (optimized_second_protection_times)')
            result = kanl.ML_func(submdl, submdl_dict, extended_result=True)
            self.log_queue.put(f'Общая ошибка: {result["loss"]}\nКоличество неселективных срабатываний: {result["non_select_count"]}\nКоличество селективных срабатываний: {result["select_count"]}\nДоля селективных срабатываний: {round(100-result["select_share"])}%\nКоличество неотключений: {result["no_off_count"]}\nСреднее время отключения: {round(result["mean_time"],2)} c')
    
        elif n_stages in [3, 4]:
            if n_stages == 3:
                two_stages = False
                self.log_queue.put('\nВводим третью ступень с параметрами между первой и второй и оптимизируем ее параметры (optimize_third_stage_settings)')
            else:
                two_stages = True
                self.log_queue.put('\nВводим третью и четвертую ступень с параметрами между первой и второй и оптимизируем их параметры (optimize_third_stage_settings)')
    
            best_sett, submdl = kar_opt.optimize_third_stage_settings(
            submdl, submdl_dict, n_trials=n_iterations, two_stages=two_stages,
            loss_params=loss_params, loss_callback=loss_callback)
            result = kanl.ML_func(submdl, submdl_dict, extended_result=True)
            self.log_queue.put(f'Общая ошибка: {result["loss"]}\nКоличество неселективных срабатываний: {result["non_select_count"]}\nКоличество селективных срабатываний: {result["select_count"]}\nДоля селективных срабатываний: {round(100-result["select_share"])}%\nКоличество неотключений: {result["no_off_count"]}\nСреднее время отключения: {round(result["mean_time"],2)} c')
    
        # После оптимизации
        try:
        #    self.log_queue.put(f"Оптимизация завершена. Лучшая ошибка: {result}")
            self.log_queue.put(f"____Оптимизация завершена____")
        except Exception as e:
            self.log_queue.put(f"Ошибка во время оптимизации: {str(e)}")
    
        finally:
            # Восстановление stdout
            sys.stdout = old_stdout
            log_output = mystdout.getvalue()
            self.log_queue.put(log_output)

    def update_ui(self):
        # Обновление лога
        try:
            while True:
                log_msg = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, log_msg + "\n")
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
    
        # Обновление графика
        try:
            updated = False
            while True:
                loss = self.loss_queue.get_nowait()
                if not hasattr(self, 'loss_values'):
                    self.loss_values = []
                self.loss_values.append(loss)
                updated = True
        except queue.Empty:
            pass
    
        if updated:
            self.ax_loss.clear()
            self.ax_loss.plot(self.loss_values, label='Loss')
            self.ax_loss.set_xlabel('Итерация')
            self.ax_loss.set_ylabel('Ошибка')
            self.ax_loss.legend()
            self.plot_canvas.draw()
    
        # Планируем следующий вызов update_ui через 100 мс
        self.after(100, self.update_ui)


    def on_resize(self, event):
        if event.widget == self:
            self.update_visualization()

    ##### ЛИСТ АНАЛИЗ ######

    def setup_analysis_page(self):
        # Основной фрейм для страницы "Анализ"
        main_frame = ttk.Frame(self.analysis_page)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Создаем три фрейма: left_frame и right_frame
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)

        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Разделяем left_frame на верхний и нижний фреймы
        upper_left_frame = ttk.Frame(left_frame)
        upper_left_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        lower_left_frame = ttk.Frame(left_frame)
        lower_left_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        # Настройка верхней левой части (таблица подрежимов с фильтрами)
        # Фильтры
        filter_frame = ttk.Frame(upper_left_frame)
        filter_frame.pack(side=tk.TOP, fill=tk.X)

        self.filter_no_off_var = tk.BooleanVar(value=True)
        self.filter_non_select_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(filter_frame, text="Неоткл КЗ", variable=self.filter_no_off_var, command=self.update_bad_modes_table).pack(side=tk.LEFT)
        ttk.Checkbutton(filter_frame, text="Неселект", variable=self.filter_non_select_var, command=self.update_bad_modes_table).pack(side=tk.LEFT)

        # Добавляем метки для суммарных показателей
        self.no_off_count_label = ttk.Label(filter_frame, text="Неоткл КЗ: 0")
        self.no_off_count_label.pack(side=tk.LEFT, padx=10)

        self.non_select_count_label = ttk.Label(filter_frame, text="Неселект: 0")
        self.non_select_count_label.pack(side=tk.LEFT, padx=10)
        
        # Таблица подрежимов
        table_frame = ttk.Frame(upper_left_frame)
        table_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        columns = ("Тип", "DI", "Линия КЗ", "Тип КЗ", "Место КЗ", "Откл линии")
        self.bad_modes_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

        for col in columns:
            self.bad_modes_tree.heading(col, text=col)
            self.bad_modes_tree.column(col, width=80, anchor='center')

        self.bad_modes_tree.pack(fill=tk.BOTH, expand=True)

        self.bad_modes_tree.bind('<<TreeviewSelect>>', self.on_bad_mode_select)

        # Настройка нижней левой части (таблица уставок)
        settings_frame = ttk.Frame(lower_left_frame)
        settings_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("id", "I0 сраб", "t сраб", "Линия", "ПС", "Ступень")
        self.settings_tree = ttk.Treeview(settings_frame, columns=columns, show='headings')

        for col in columns:
            self.settings_tree.heading(col, text=col)
            self.settings_tree.column(col, width=80, anchor='center')

        self.settings_tree.pack(fill=tk.BOTH, expand=True)

        self.settings_tree.bind('<Double-1>', self.on_setting_double_click)

        recalculate_button = ttk.Button(lower_left_frame, text="Пересчет", command=self.on_recalculate)
        recalculate_button.pack(pady=5)

        # Настройка правой части (визуализация графа сети)
        self.anl_canvas_frame = ttk.Frame(right_frame)
        self.anl_canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.anl_canvas = tk.Canvas(self.anl_canvas_frame, bg='white')
        self.anl_canvas.pack(fill=tk.BOTH, expand=True)
        '''
        control_frame = ttk.Frame(right_frame)
        control_frame.pack(fill=tk.X)

        ttk.Label(control_frame, text="Время:").pack(side=tk.LEFT)

        self.time_scale_var = tk.IntVar()
        self.time_scale = ttk.Scale(control_frame, from_=0, to=0, variable=self.time_scale_var, orient=tk.HORIZONTAL, command=self.on_time_scale_change)
        self.time_scale.pack(fill=tk.X, expand=True)
        '''
        # Удаляем ползунок времени и добавляем кнопки
        control_frame = ttk.Frame(right_frame)
        control_frame.pack(fill=tk.X)

        self.time_label = ttk.Label(control_frame, text="Время: До КЗ")
        self.time_label.pack(side=tk.LEFT, padx=5)

        back_button = ttk.Button(control_frame, text="Назад", command=self.decrease_time_index)
        back_button.pack(side=tk.LEFT, padx=5)

        next_button = ttk.Button(control_frame, text="Вперед", command=self.increase_time_index)
        next_button.pack(side=tk.LEFT, padx=5)

        self.time_index = 0  # Изначально выставляем на 0
    def decrease_time_index(self):
        """Уменьшить индекс времени и обновить график."""
        if self.time_index > 0:
            self.time_index -= 1
            self.update_time_label()
            self.draw_network_graph(self.time_index)

    def increase_time_index(self):
        """Увеличить индекс времени и обновить график."""
        if self.time_index < len(self.smdl_dict) - 1:
            self.time_index += 1
            self.update_time_label()
            self.draw_network_graph(self.time_index)
    
    def update_time_label(self):
        """Обновить метку времени на основе текущего индекса."""
        if self.time_index == 0:
            self.time_label.config(text="Время: До КЗ")
        else:
            self.time_label.config(text=f"Время: {round(self.smdl_dict[self.time_index]['t'],1)}")


    # Обновление таблицы подрежимов с фильтрами
    def update_bad_modes_table(self):
        # Очищаем текущие данные
        for item in self.bad_modes_tree.get_children():
            self.bad_modes_tree.delete(item)

        # Получаем данные о плохих подрежимах
        bad_sm_dict, self.prot_work = show_bad_results(self.mdl, self.submdl_dict)
        
        # Инициализируем счетчики
        no_off_count = 0
        non_select_count = 0
        
        # Фильтры
        filter_no_off = self.filter_no_off_var.get()
        filter_non_select = self.filter_non_select_var.get()

        # Заполняем таблицу и считаем количество неселективных срабатываний и неотключений КЗ
        for i in bad_sm_dict:
            entry = bad_sm_dict[i]
            if entry['type'] == 'Неоткл КЗ':
                no_off_count += 1
            elif entry['type'] == 'Неселект':
                non_select_count += 1

            if (entry['type'] == 'Неоткл КЗ' and filter_no_off) or (entry['type'] == 'Неселект' and filter_non_select):
                values = (entry['type'], entry['id'], entry['line_kz'], entry['kz_type'], entry['percent'], entry['p_off'])
                self.bad_modes_tree.insert('', tk.END, values=values)

        # Обновляем текстовые метки с количеством
        self.no_off_count_label.config(text=f"Неоткл КЗ: {no_off_count}")
        self.non_select_count_label.config(text=f"Неселект: {non_select_count}")

    # Обработка выбора подрежима в таблице
    def on_bad_mode_select(self, event):
        selected_item = self.bad_modes_tree.selection()
        if selected_item:
            item_values = self.bad_modes_tree.item(selected_item[0])['values']
            sm_id = item_values[1]  # ID подрежима
            self.update_graph_visualization(sm_id)

    # Визуализация сети во времени
    def update_graph_visualization(self, sm_id):
        # Получаем список состояний сети во времени
        self.smdl_dict = make_G_list(self.mdl, self.submdl_dict, sm_id, self.prot_work)
        # Отображаем начальное состояние
        self.draw_network_graph(time_index=0)
    '''
    def on_time_scale_change(self, value):
        time_index = int(float(value))
        self.draw_network_graph(time_index)
    '''
    def draw_network_graph(self, time_index):
        """Отрисовать граф сети для указанного времени."""
        self.anl_canvas.delete("all")
        
        # Выбираем модель в зависимости от time_index
        sm = self.smdl_dict[time_index]['sm']
        sm.Calc()  # Выполняем расчет параметров модели
        G = sm.G
    
        if not G.nodes:
            print("No nodes in graph.")
            return
    
        anl_canvas_width = self.anl_canvas.winfo_width()
        anl_canvas_height = self.anl_canvas.winfo_height()
        node_positions = {node: data['pos'] for node, data in G.nodes(data=True) if 'pos' in data}
        
        if not node_positions:
            print("No node positions available.")
            return
    
        # Масштабирование и преобразование координат
        min_x = min(x for x, y in node_positions.values())
        max_x = max(x for x, y in node_positions.values())
        min_y = min(y for x, y in node_positions.values())
        max_y = max(y for x, y in node_positions.values())
        
        padding = 40
        usable_width = max(1, anl_canvas_width - 2 * padding)
        usable_height = max(1, anl_canvas_height - 2 * padding)
        
        scale_x = usable_width / max(1, max_x - min_x)
        scale_y = usable_height / max(1, max_y - min_y)
        scale = min(scale_x, scale_y)
        
        def to_anl_canvas_coords(x, y):
            anl_canvas_x = padding + (x - min_x) * scale
            anl_canvas_y = anl_canvas_height - (padding + (y - min_y) * scale)
            return int(anl_canvas_x), int(anl_canvas_y)
    
        # Определение цветов и размеров узлов
        node_colors = {}
        node_sizes = {}
        for n in sm.bn:
            kz_name = n.qp.name
            node_colors[kz_name] = 'red'
            node_sizes[kz_name] = 10  # Увеличенный размер для узлов КЗ
        
        for q in sm.bp:
            if q.E[0] != 0:
                gen_name = q.name + '_0'
                node_colors[gen_name] = 'darkblue'
                node_sizes[gen_name] = 5
        '''
        # Отрисовка рёбер и их меток
        for p in sm.bp:
            q1_name = p.q1.name if p.q1 != 0 else p.name + '_0'
            q2_name = p.q2.name if p.q2 != 0 else p.name + '_0'
    
            I0 = p.res1(['I0'], 'M')['I0']
            ang = p.res1(['I0'], '<f')['I0']
    
            start = to_anl_canvas_coords(*node_positions[q1_name])
            end = to_anl_canvas_coords(*node_positions[q2_name])
    
            # Определение направления стрелки
            if ((-20 <= ang <= 160) or (340 <= ang <= 360)):
                arrow = tk.LAST
            else:
                arrow = tk.FIRST
                start, end = end, start  # Меняем местами начало и конец для правильного направления стрелки
    
            try:
                I0 = round(I0)
            except:
                I0 = 0
    
            line_color = "blue" if G.edges[q1_name, q2_name].get("is_operational", True) else "red"
            self.anl_canvas.create_line(start[0], start[1], end[0], end[1], fill=line_color, width=2, arrow=arrow)
        
            # Вычисление угла наклона линии для размещения текста
            angle = math.atan2(end[1] - start[1], end[0] - start[0])
            #angle = math.atan2(- end[1] + start[1], - end[0] + start[0])
            text_angle = math.degrees(angle)
            if 90 < text_angle <= 270:
                text_angle += 180
    
            mid_x = (start[0] + end[0]) / 2
            mid_y = (start[1] + end[1]) / 2
            self.anl_canvas.create_text(mid_x, mid_y, text=f"{p.name}\nI0={I0}", font=("Arial", 8), angle=text_angle)
            '''
            # Внутри функции draw_network_graph, заменить часть с отрисовкой рёбер и их меток:

        # Отрисовка рёбер и их меток
        for p in sm.bp:
            q1_name = p.q1.name if p.q1 != 0 else p.name + '_0'
            q2_name = p.q2.name if p.q2 != 0 else p.name + '_0'
        
            I0 = p.res1(['I0'], 'M')['I0']
            ang = p.res1(['I0'], '<f')['I0']
        
            start = to_anl_canvas_coords(*node_positions[q1_name])
            end = to_anl_canvas_coords(*node_positions[q2_name])
        
            # Определение направления стрелки
            if ((-20 <= ang <= 160) or (340 <= ang <= 360)):
                arrow = tk.LAST
            else:
                arrow = tk.FIRST
                start, end = end, start  # Меняем местами начало и конец для правильного направления стрелки
        
            try:
                I0 = round(I0)
            except:
                I0 = 0
        
            line_color = "blue" if G.edges[q1_name, q2_name].get("is_operational", True) else "red"
            self.anl_canvas.create_line(start[0], start[1], end[0], end[1], fill=line_color, width=2, arrow=arrow)
        
            # Вычисление угла наклона линии для размещения текста
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            angle = math.atan2(dy, dx)
            text_angle = math.degrees(angle)
        
            # Корректировка угла для правильной ориентации текста
            if -90 <= text_angle <= 90:
                text_angle = -text_angle
            else:
                text_angle = 180 - text_angle
        
            mid_x = (start[0] + end[0]) / 2
            mid_y = (start[1] + end[1]) / 2
            
            # Создаем текст с правильным углом наклона
            text = self.anl_canvas.create_text(mid_x, mid_y, text=f"{p.name}\nI0={I0}", font=("Arial", 8), angle=text_angle)
            
            # Получаем границы текста
            bbox = self.anl_canvas.bbox(text)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Смещаем текст перпендикулярно линии
            offset = 0  # Расстояние смещения от линии
            perpendicular_angle = angle + math.pi/2
            offset_x = offset * math.cos(perpendicular_angle)
            offset_y = offset * math.sin(perpendicular_angle)
            
            self.anl_canvas.move(text, offset_x, offset_y)
    
        # Отрисовка взаимной индукции
        for m in sm.bm:
            line1, line2 = m.p1, m.p2
            x11, y11 = to_anl_canvas_coords(*(node_positions[line1.q1.name] if line1.q1 != 0 else (0, 0)))
            x12, y12 = to_anl_canvas_coords(*(node_positions[line1.q2.name] if line1.q2 != 0 else (0, 0)))
            x21, y21 = to_anl_canvas_coords(*(node_positions[line2.q1.name] if line2.q1 != 0 else (0, 0)))
            x22, y22 = to_anl_canvas_coords(*(node_positions[line2.q2.name] if line2.q2 != 0 else (0, 0)))
    
            mid1_x, mid1_y = (x11 + x12) / 2, (y11 + y12) / 2
            mid2_x, mid2_y = (x21 + x22) / 2, (y21 + y22) / 2
            self.anl_canvas.create_line(mid1_x, mid1_y, mid2_x, mid2_y, fill="gray", dash=(2, 2))
    
        # Отрисовка узлов
        for node, (x, y) in node_positions.items():
            anl_canvas_x, anl_canvas_y = to_anl_canvas_coords(x, y)
            color = node_colors.get(node, 'lightblue')
            size = node_sizes.get(node, 5)
            self.anl_canvas.create_oval(anl_canvas_x-size, anl_canvas_y-size, anl_canvas_x+size, anl_canvas_y+size, fill=color, outline="black")
            self.anl_canvas.create_text(anl_canvas_x, anl_canvas_y-15, text=str(node), font=("Arial", 10, "bold"))
    
        self.anl_canvas.update()


    # Обновление таблицы уставок
    def update_settings_table(self):
        # Очищаем текущие данные
        for item in self.settings_tree.get_children():
            self.settings_tree.delete(item)

        # Получаем уставки
        self.set_dict = kanl.set_to_dict(self.mdl, pq=True)

        # Заполняем таблицу
        for index in self.set_dict:
            entry = self.set_dict[index]
            values = (index, entry['I0_сраб'], entry['t_сраб'], entry['line'], entry['q'], entry['stage'])
            self.settings_tree.insert('', tk.END, values=values)

    # Обработка двойного клика по уставке для редактирования
    def on_setting_double_click(self, event):
        selected_item = self.settings_tree.selection()
        if selected_item:
            item = selected_item[0]
            values = self.settings_tree.item(item, 'values')
            index = int(values[0])

            # Открываем окно редактирования
            edit_window = tk.Toplevel(self)
            edit_window.title("Редактирование уставок")

            ttk.Label(edit_window, text="I0:").grid(row=0, column=0, padx=5, pady=5)
            i0_var = tk.DoubleVar(value=values[1])
            ttk.Entry(edit_window, textvariable=i0_var).grid(row=0, column=1, padx=5, pady=5)

            ttk.Label(edit_window, text="t:").grid(row=1, column=0, padx=5, pady=5)
            t_var = tk.DoubleVar(value=values[2])
            ttk.Entry(edit_window, textvariable=t_var).grid(row=1, column=1, padx=5, pady=5)

            def save_settings():
                # Применяем новые уставки
                self.mdl.bd[index+1].edit(I0=i0_var.get(), t=t_var.get())
                # Обновляем таблицу
                self.update_settings_table()
                edit_window.destroy()

            ttk.Button(edit_window, text="Сохранить", command=save_settings).grid(row=2, column=0, columnspan=2, pady=10)

    # Пересчет плохих подрежимов с новыми уставками
    def on_recalculate(self):
        # Пересчитываем плохие подрежимы с новыми уставками
        #self.setup_analysis_page()
        self.update_bad_modes_table()
        self.update_settings_table()
        #messagebox.showinfo("Пересчет", "Пересчет завершен.")


if __name__ == "__main__":
    app = PowerGridOptimizationApp()
    app.mainloop()