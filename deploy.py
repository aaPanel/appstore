import paramiko
import os
from dotenv import load_dotenv


def load_config():
    """从.env文件加载配置"""
    load_dotenv()  # 加载.env文件
    
    return {
        "host": os.getenv('SSH_HOST', '192.168.10.194'),
        "port": int(os.getenv('SSH_PORT', '22')),
        "username": os.getenv('SSH_USERNAME', 'root'),
        "password": os.getenv('SSH_PASSWORD', '')
    }


def upload_dir(sftp, local_dir, remote_dir):
    # 创建远程目录（如果不存在）
    try:
        sftp.mkdir(remote_dir)
    except IOError:
        pass  # 已存在则忽略
    
    # 遍历本地目录
    for item in os.listdir(local_dir):
        local_path = os.path.join(local_dir, item)
        remote_path = os.path.join(remote_dir, item).replace('\\', '/')  # 统一路径分隔符
        
        if os.path.isfile(local_path):
            sftp.put(local_path, remote_path)  # 上传文件
        elif os.path.isdir(local_path):
            upload_dir(sftp, local_path, remote_path)  # 递归上传子目录


def upload_file(sftp, local_file, remote_file):
    # 创建远程目录（如果不存在）
    remote_dir = os.path.dirname(remote_file)
    try:
        sftp.mkdir("/www/dk_project/dk_app/templates")
        sftp.mkdir(remote_dir)
    except IOError:
        pass  # 已存在则忽略
    
    sftp.put(local_file, remote_file)  # 上传单个文件


def main(appname):
    # 加载配置
    config = load_config()
    
    mappings = [
        ('pkg/apps.json', '/www/dk_project/dk_app/apps.json'),
        ('apptags.json', '/www/dk_project/dk_app/apptags.json')
    ]
    
    if isinstance(appname, str):
        mappings.append(('apps/{appname}/{appname}'.format(appname=appname), f'/www/dk_project/dk_app/templates/{appname}'))
    elif isinstance(appname, list):
        for name in appname:
            mappings.append(('apps/{appname}/{appname}'.format(appname=name), f'/www/dk_project/dk_app/templates/{name}'))
    
    # 从配置文件读取连接信息
    host = config['host']
    port = config['port']
    username = config['username']
    password = config['password']
    
    transport = paramiko.Transport((host, port))
    transport.connect(username=username, password=password)
    sftp = paramiko.SFTPClient.from_transport(transport)
    
    # 执行每个映射的上传
    for local_path, remote_path in mappings:
        if os.path.isfile(local_path):
            upload_file(sftp, local_path, remote_path)
        elif os.path.isdir(local_path):
            upload_dir(sftp, local_path, remote_path)
        else:
            print(f"警告: {local_path} 不是有效文件或目录，跳过。")
    
    # 关闭连接
    sftp.close()
    transport.close()
    
    print("上传完成")
    

if __name__ == '__main__':
    main("calcom")