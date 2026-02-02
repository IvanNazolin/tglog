import psutil
from tqdm import tqdm
from time import sleep

with tqdm(total=100, desc='CPU %', position=0) as cpubar, \
     tqdm(total=100, desc='RAM %', position=1) as rambar, \
     tqdm(total=100, desc='SWAP %', position=2) as swapbar, \
     tqdm(total=100, desc='DISK %', position=3) as diskbar:

    while True:
        # CPU %
        cpu = psutil.cpu_percent(interval=None)

        # RAM %
        vm = psutil.virtual_memory()
        ram_percent = vm.percent
        ram_used = vm.used / (1024**3)
        ram_total = vm.total / (1024**3)

        # SWAP %
        swap = psutil.swap_memory()
        swap_percent = swap.percent
        swap_used = swap.used / (1024**3)
        swap_total = swap.total / (1024**3)

        # Disk %
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_used = disk.used / (1024**3)
        disk_total = disk.total / (1024**3)

        # Обновляем прогресс-бары
        cpubar.n = cpu
        rambar.n = ram_percent
        swapbar.n = swap_percent
        diskbar.n = disk_percent

        # Обновляем отображение
        cpubar.set_postfix({"val": f"{cpu:.1f}%"})
        rambar.set_postfix({"used": f"{ram_used:.1f}G/{ram_total:.1f}G"})
        swapbar.set_postfix({"used": f"{swap_used:.1f}G/{swap_total:.1f}G"})
        diskbar.set_postfix({"used": f"{disk_used:.1f}G/{disk_total:.1f}G"})

        cpubar.refresh()
        rambar.refresh()
        swapbar.refresh()
        diskbar.refresh()

        sleep(0.5)