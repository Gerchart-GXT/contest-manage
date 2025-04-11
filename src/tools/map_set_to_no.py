import pandas as pd
import numpy as np

# 读取 Excel 文件中的座位表
file_path = 'seat_table.xlsx'  # 替换为你的 Excel 文件路径
seat_df = pd.read_excel(file_path, header=None)  # 假设没有表头

# 将 DataFrame 转换为 NumPy 数组
seat_array = seat_df.to_numpy()

# 获取所有非 NaN 且非零元素的唯一值并排序
unique_values = np.unique(seat_array[~np.isnan(seat_array) & (seat_array != 0)])
unique_values.sort()

# 创建一个映射字典，将原始值映射到新的离散化值
mapping = {value: idx + 1 for idx, value in enumerate(unique_values)}

# 创建一个新的数组来存储离散化后的值，初始化为 NaN
discretized_array = np.full_like(seat_array, np.nan, dtype=float)

# 遍历原始数组，根据映射字典进行离散化
for i in range(seat_array.shape[0]):
    for j in range(seat_array.shape[1]):
        if not np.isnan(seat_array[i, j]) and seat_array[i, j] != 0:  # 只处理非 NaN 且非零值
            discretized_array[i, j] = mapping[seat_array[i, j]]

# 将离散化后的数组转换为 DataFrame
discretized_df = pd.DataFrame(discretized_array)

# 将离散化后的结果保存到新的 Excel 文件
output_file_path = 'discretized_seat_table.xlsx'  # 输出文件路径
discretized_df.to_excel(output_file_path, index=False, header=False)

print("离散化完成！结果已保存到:", output_file_path)