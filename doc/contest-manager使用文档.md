# 比赛管理程序使用手册

## 简介

本软件基于C/S架构进行设计，每台考生机器上部署一台Web服务器，管理机通过http请求对考生机器进行管理，实现如下主干功能：

1. 考场机器连通情况查询（基于Ping命令）
2. 考生机客户端基本信息配置，包括且不限于考生姓名，准考证号等
3. 考生机客户端连通情况查询
4. 考生机信息提示框打开/关闭，提示信息支持`HTML/CSS/JS`
5. 考生机系统命令执行
6. 考生机客户端日志获取
7. 按ip/考生号/考生姓名/考试组，正则选取/过滤考生机器

并计划提供试验功能：

1. 基于倍增的考生机文件下发/接收
2. 考生机代码备份至数据盘
3. 考生机活跃窗口获取域活跃进程查询

## 安装说明

### 考生机器程序安装

1. 下载最新版本客户端`lanqiao_client.zip`压缩包
2. 将压缩包`lanqiao_client.zip`通过管理机/教师机下发至所有学生机
3. 将`unzip.bat`通过管理机/教师机下发至所有学生机
4. 所有学生机运行`unzip.bat`批处理脚本，该脚本会将学生客户端解压至`C:\lanqiao\client`

至此，学生机程序安装完成

### 考生机器程序启动/停止

* 在`C:\lanqiao\client`下有`start_client.bat`和`stop_client.bat`两批处理脚本
* 启动/重启请让所有学生机运行`start_client.bat`，
* 停止请让所有学生机运行`stop_client.bat`

### 管理机/教师机程序安装

1. 安装最新版本`Python`和`pip`，并配置好环境变量，保证联网
2. 下载最新版本源码，建议使用`git clone`

3. 进入源码目录，使用`python -m venv env`创建虚拟环境，并激活虚拟环境
4. `pip`安装`requirement.txt`
5. 进入`src/manager`目录，阅读下文使用说明，使用`python main.py <command>`进行使用

## 使用说明

### 管理机配置

#### 机房IP段配置

1. 进入`src/manager/main.py`
2. 修改机房名称`ROOM_ID = "101"`
3. 修改`IP_RANGE = "192.168.1.1-150"`进行ip段设置
4. 修改本地ip `LOCAL_IP = ""`

#### 考生名单导入

1. 在`src/manager/`下新建`client.xlsx`

2. 修改名单变量名映射

    1. 进入`src/manager/main.py`

    2. 修改，字典value为表格表头名，

        ```python
        CLIENT_EXCEL_TITLE = {
            "user_id": "考生准考证号", 
            "user_name": "考生姓名",
            "user_room": "考生考场",
            "user_ip": "考生机器IP",
            "group_id": "组别",
            "exam_id": "考试编号"
        }
        ```

3. 如需更改名单路径可更改`CLIENT_EXCEL_PATH = "./client.xlsx"`

#### 正则Filter配置

* 为满足指定机器的精准控制，引入正则过滤，配置文件位于`src/manager/filter.json`，格式如下（注意特殊符号的转义）：

    ```json
    {
        "active": true,
        "ip": {
            "reg": "^((25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\\.){3}(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])$"
        },
        "user_name":{
            "reg": "gerchart"
        },
        "user_id": {
            "reg": ".*"
        },
        "group_id": {
            "reg": "C/C++"
        }
    }
    ```

    * `active`用于开关正则过滤器
    * `reg`字段输入正则表达式

* 本过滤器生效于一下所有控制方法，若不匹配在日志中会有`2025-04-07 23:31:20,036 - logger - ERROR - Regular expr not match! 10.0.0.25 gerchart!`字样输出，请留意

### 日志系统

* 基于`python`的`logger`模块，服务端和客户端均开发了日志系统，日志存放于文件统计目录的`logs/*.log`下，同步输出在命令行，以供调试和历史记录查看

```
2025-04-07 23:16:22,821 - logger - INFO - Utility Init.
2025-04-07 23:16:22,867 - logger - INFO - Read client Excel ./client.xlsx successfully!
2025-04-07 23:16:22,867 - logger - INFO - Read file from filter.json
2025-04-07 23:16:22,867 - logger - INFO - Read file successfully : filter.json
2025-04-07 23:16:22,867 - logger - INFO - Ping test for 10.0.0.23-25
2025-04-07 23:16:23,881 - logger - INFO - Available ip count: 1
2025-04-07 23:16:23,881 - logger - WARNING - 10.0.0.23 is lost
2025-04-07 23:16:23,881 - logger - WARNING - 10.0.0.24 is lost
2025-04-07 23:16:23,881 - logger - INFO - Ping: Available 1, loss 2, total 3
```

### 初始化

#### 考生机连通性测试

* 运行`python main.py ping`等待运行结束，得到当前可通ip数和不通ip

    ```
    2025-04-07 22:21:27,181 - logger - INFO - Read client Excel ./client.xlsx successfully!
    2025-04-07 22:21:27,182 - logger - INFO - Ping test for 10.0.0.23-25
    2025-04-07 22:21:28,198 - logger - INFO - Available ip count: 1
    2025-04-07 22:21:28,200 - logger - WARNING - 10.0.0.23 is lost
    2025-04-07 22:21:28,200 - logger - WARNING - 10.0.0.24 is lost
    2025-04-07 22:21:28,200 - logger - INFO - Ping: Available 1, loss 2, total 3
    ```

#### 进行考生与机器的绑定

1. 确保`src/manager/`下已导入名单，并设置好别名

2. 运行`python main.py update-client-list`等待运行结束，查看程序输出/日志或名单文件可得到绑定结果

    ```
    2025-04-07 22:26:31,676 - logger - INFO - Utility Init.
    2025-04-07 22:26:31,727 - logger - INFO - Read client Excel ./client.xlsx successfully!
    2025-04-07 22:26:31,727 - logger - INFO - Ping test for 10.0.0.23-25
    2025-04-07 22:26:32,743 - logger - INFO - Available ip count: 1
    2025-04-07 22:26:32,746 - logger - INFO - Client count 1
    2025-04-07 22:26:32,746 - logger - INFO - Mapping gerchart(123456) to 10.0.0.25
    2025-04-07 22:26:32,779 - logger - INFO - Save client Excel ./client.xlsx successfully!
    ```

3. 完成初次绑定后根据实际情况进行调整即可，如果有机器需要更换，直接修改名单接口，修改后请勿运行`update-client-list`，否则会重新绑定
4. 若考生数多于可用机器数，则会将多余考生绑定至`None`
5. 本绑定只会修改本地的考生名单，不会讲信息下发至考生机，下发请见`考生信息下发`。

#### 考生信息下发

* 在完成绑定后，确认绑定信息无误，建议首先备份考生名单，防止误操作运行`update-client-list`覆盖

1. 运行`python main.py set-client-info`，即可将考生信息下发至客户端，完成下发后，客户端目录的`user-info.json`将为考生信息

    ```
    2025-04-07 22:32:32,986 - logger - INFO - Utility Init.
    2025-04-07 22:32:33,035 - logger - INFO - Read client Excel ./client.xlsx successfully!
    2025-04-07 22:32:33,035 - logger - INFO - Set user http://10.0.0.25:8088/client/user, {'user_id': 123456, 'user_name': 'gerchart', 'user_room': 101, 'user_ip': '10.0.0.25', 'group_id': 'C/C++', 'exam_id': 'laoqiao'}
    2025-04-07 22:32:33,050 - logger - INFO - Set client info: Success 1, Fail 0, total 1
    ```

### 考生客户端连接性测试

* 客户端连通性测试测试的是考生客户端的工作状态，请与前文ping测试区分

1. 运行`python main.py connect-check`，查看程序输出/日志获取测试结果

    ```
    2025-04-07 22:36:23,348 - logger - INFO - Utility Init.
    2025-04-07 22:36:23,413 - logger - INFO - Read client Excel ./client.xlsx successfully!
    2025-04-07 22:36:23,413 - logger - INFO - Connect to http://10.0.0.25:8088/client/connect
    2025-04-07 22:36:23,423 - logger - INFO - Connect to 10.0.0.25 gerchart successfully!
    2025-04-07 22:36:23,426 - logger - INFO - Connect client info: Success 1, Fail 0, total 1
    ```

### 考生客户端状态与日志获取

* 通过获取客户端状态与日志可以清楚查看考生客户端的工作历史
* 日志获取为最后100条记录，若机房机器过多可能会短暂占用带宽

#### 状态获取

1. 运行`python main.py get-client-status`，查看程序输出/日志获取测试结果

    ```
    2025-04-07 22:40:48,183 - logger - INFO - Utility Init.
    2025-04-07 22:40:48,247 - logger - INFO - Read client Excel ./client.xlsx successfully!
    2025-04-07 22:40:48,248 - logger - INFO - Get status http://10.0.0.25:8088/client/status
    2025-04-07 22:40:48,255 - logger - INFO - Get client status 10.0.0.25  gerchart successfully!
    2025-04-07 22:40:48,256 - logger - INFO - Save file to client-status/25-04-07-22:40:48.json
    2025-04-07 22:40:48,256 - logger - INFO - Save file successfully : client-status/25-04-07-22:40:48.json
    2025-04-07 22:40:48,256 - logger - INFO - Get client status: Success 1, Fail 0, total 1
    ```

2. 客户端状态会存储在`src/manager/client-status/[Timestamp].json`，打开查看即可

    ```json
    [
        [
            {
                "user_id": 123456,
                "user_name": "gerchart",
                "user_room": 101,
                "user_ip": "10.0.0.25",
                "group_id": "C/C++",
                "exam_id": "laoqiao"
            },
            {
                "mesg": "Get status successfully",
                "metadata": {
                    "active_progress": [],
                    "timestamp": "2025-04-07T22:40:48.255111"
                },
                "status": "success",
                "user_data": {
                    "exam_id": "laoqiao",
                    "group_id": "C/C++",
                    "user_id": 123456,
                    "user_ip": "10.0.0.25",
                    "user_name": "gerchart",
                    "user_room": 101
                }
            }
        ]
    ]
    ```

#### 日志获取

1. 运行`python main.py get-client-log`，查看程序输出/日志获取测试结果

    ```
    2025-04-07 22:42:29,059 - logger - INFO - Utility Init.
    2025-04-07 22:42:29,130 - logger - INFO - Read client Excel ./client.xlsx successfully!
    2025-04-07 22:42:29,130 - logger - INFO - Get log http://10.0.0.25:8088/client/log
    2025-04-07 22:42:29,138 - logger - INFO - Get client logs 10.0.0.25  gerchart successfully!
    2025-04-07 22:42:29,138 - logger - INFO - Save file to client-log/25-04-07-22:42:29.json
    2025-04-07 22:42:29,138 - logger - INFO - Save file successfully : client-log/25-04-07-22:42:29.json
    2025-04-07 22:42:29,138 - logger - INFO - Get client log: Success 1, Fail 0, total 1
    ```

2. 客户端日志会存储在`src/manager/client-log/[Timestamp].json`，打开查看即可

    ```
    [
        [
            {
                "user_id": 123456,
                "user_name": "gerchart",
                "user_room": 101,
                "user_ip": "10.0.0.25",
                "group_id": "C/C++",
                "exam_id": "laoqiao"
            },
            {
                "log_content": [
                    "2025-04-07 22:32:15,332 - logger - INFO - Utility Init.\n",
                    "2025-04-07 22:32:15,332 - logger - INFO - Get local ipv4!\n",
                    "2025-04-07 22:32:15,332 - logger - INFO - Get local ipv4 successfully: 10.0.0.25\n",
                    "2025-04-07 22:32:15,333 - logger - INFO - Generate API-KEY: dd18e34fe5634c7b9414cef1ab608081\n",
                    "2025-04-07 22:32:15,333 - logger - INFO - Save file to ./api-key.json\n",
                    "2025-04-07 22:32:15,333 - logger - INFO - Save file successfully : ./api-key.json\n",
                    "2025-04-07 22:32:15,333 - logger - INFO - Read file from ./user-info.json\n",
                    "2025-04-07 22:32:15,333 - logger - INFO - Read file successfully : ./user-info.json\n",
                    "2025-04-07 22:32:15,333 - logger - INFO - Flask server start!\n",
                    "2025-04-07 22:32:16,953 - logger - INFO - Save file to ./user-info.json\n",
                    "2025-04-07 22:32:16,953 - logger - INFO - Save file successfully : ./user-info.json\n",
                    "2025-04-07 22:32:16,953 - logger - INFO - User info saved successfully: {'user_id': 123456, 'user_name': 'gerchart', 'user_room': 101, 'user_ip': '10.0.0.25', 'group_id': 'C/C++', 'exam_id': 'laoqiao'}\n",
                    "2025-04-07 22:32:33,043 - logger - INFO - Save file to ./user-info.json\n",
                    "2025-04-07 22:32:33,043 - logger - INFO - Save file successfully : ./user-info.json\n",
                    "2025-04-07 22:32:33,043 - logger - INFO - User info saved successfully: {'user_id': 123456, 'user_name': 'gerchart', 'user_room': 101, 'user_ip': '10.0.0.25', 'group_id': 'C/C++', 'exam_id': 'laoqiao'}\n",
                    "2025-04-07 22:40:48,254 - logger - INFO - Status retrieved successfully for user: {'user_id': 123456, 'user_name': 'gerchart', 'user_room': 101, 'user_ip': '10.0.0.25', 'group_id': 'C/C++', 'exam_id': 'laoqiao'}\n"
                ],
                "mesg": "Log file retrieved successfully",
                "status": "success"
            }
        ]
    ]
    ```

### 考生机信息提示框开启/关闭

* 本方案基于QT，理论上所有系统均支持，渲染的页面尊循`HTML`规范，支持自定义字体大小，默认最大化置顶，由管理端统一开启/关闭窗口（也可手动关闭）效果如图：![1744040855127.JPG](https://picture.imgxt.com/local/1/2025/04/07/67f3f398e12c7.png)
* 每个窗口通过唯一的`window_id`进行标识，同一标识页面不可重复开启，若重复调用除非手动关闭，否则只会显示第一次调用内容

1. 运行`python main.py open-info-window <window_id>`，`window_id`为正整数，此时会从`src/manager/`下读取`window.json`文件内容，`window.json`文件格式如下：

    ```json
    {
        "title": "考生信息",
        "content": "f\"<h1>第十六届蓝桥杯大赛江苏省赛（软件类）–河海大学赛点</h1><h2>考场号: {client[\"user_room\"]}</h2><h2>考生姓名：{client[\"user_name\"]}</h2><h2>考生准考证号：{client[\"user_id\"]}</h2><h2>考生组别：{client[\"group_id\"]}</h2><h3>请遵守考场纪律，严禁作弊，祝你考试顺利！</h3><p>&nbsp;</p>\"",
        "front_size": 50
    }
    ```

    * `content`字段请使用`f-string`，可根据实际需求嵌入考生信息，如需显示更多信息请阅读源码`def open_info_window(title, content, window_id, front_size, max_workers=50)`函数部分

2. 开启后可以运行``python main.py close-info-window <window_id>`进行关闭，`window_id`请保持与开启一致

### 考生机命令执行

* 命令执行权限取决于考生机用户权限
* 配合正则filter可以实现对单独机器或某组机器的指令单独执行，适合于蓝桥杯等不用比赛环境的批量配置，同时也适用于批量检测环境配置结果等

1. 运行`python main.py run-command`，此时会从`src/manager/`下读取`command.json`文件内容，`command.json`文件格式如下：

    ```json
    {
        "command": "ping 127.0.0.1 -c 4"
    }
    ```