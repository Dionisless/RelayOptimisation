# RelayOptimisation
Программа оптимизации токовых защит нулевой последовательности. 

Анализирует и и оценивает срабатывание защит в множестве подрежимов сети и использует алгоритм оптимизации для подбора уставок.

![image](https://github.com/user-attachments/assets/e6c79a98-35b9-494a-b71e-4c00dff67761)
Общая структура оптимизации


## Файлы
- GUI.py - код GUI программы
- mrtkz3.py - модификация библиотеки mrtkz3 (https://github.com/aspirmk/mrtkz)
- kar_mrtkz.py - функции для работы с моделью сети
- kar_analyse.py - функции для анализа и оценки страбатываний защит
- kar_optimisation_pypeline.py - функции оптимизации защит
