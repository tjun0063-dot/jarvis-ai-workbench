import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'work'/'vm-tools'))
import pycdlib
source=Path(sys.argv[1]).resolve();target=Path(sys.argv[2]).resolve()
iso=pycdlib.PyCdlib();iso.new(udf='2.60',interchange_level=3,vol_ident='JARVIS_SETUP')
paths={source:'/'};count=0
for directory,dirs,files in os.walk(source):
    parent=Path(directory);dirs.sort();files.sort()
    for name in dirs:
        count+=1;child=parent/name;paths[child]=paths[parent].rstrip('/')+f'/D{count:07d}'
        udf='/'+child.relative_to(source).as_posix()
        iso.add_directory(iso_path=paths[child],udf_path=udf)
    for name in files:
        count+=1;child=parent/name;logical=paths[parent].rstrip('/')+f'/F{count:07d};1'
        iso.add_file(str(child),iso_path=logical,udf_path='/'+child.relative_to(source).as_posix())
iso.write(str(target));iso.close()
print('部署 ISO 已生成：'+str(target))
