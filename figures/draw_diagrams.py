"""Vector drawing primitives; copied into each independent project generator."""
import argparse
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, Circle, FancyArrowPatch

plt.rcParams.update({'font.family':'STIXGeneral', 'mathtext.fontset':'stix',
                     'font.size':9, 'pdf.fonttype':42, 'ps.fonttype':42,
                     'text.usetex':False, 'axes.unicode_minus':False})
CM = 1 / 2.54

class Drawing:
    def __init__(self, bounds):
        x0,y0,x1,y1 = bounds
        self.fig = plt.figure(figsize=((x1-x0)*CM,(y1-y0)*CM))
        self.ax = self.fig.add_axes([0,0,1,1], xlim=(x0,x1), ylim=(y0,y1))
        self.ax.set_aspect('equal'); self.ax.axis('off')
        self.nodes = {}
        self.labels = []

    def text(self,x,y,label,size=9,ha='center',va='center'):
        artist=self.ax.text(x,y,label,fontsize=size,ha=ha,va=va,
                            linespacing=1.15,clip_on=False,zorder=4)
        self.labels.append([artist,None])
        return artist

    def box(self,name,x,y,w,h,label,dashed=False,shape='rect',size=9):
        style = {'edgecolor':'black','facecolor':'white','linewidth':.55,
                 'linestyle':(0,(4,3)) if dashed else 'solid', 'zorder':2}
        if shape == 'diamond':
            obj = Polygon([(x-w/2,y),(x,y+h/2),(x+w/2,y),(x,y-h/2)],**style)
        elif shape == 'circle': obj = Circle((x,y),w/2,**style)
        else: obj = Rectangle((x-w/2,y-h/2),w,h,**style)
        self.ax.add_patch(obj); self.text(x,y,label,size)
        self.labels[-1][1]=(x-w/2,y-h/2,x+w/2,y+h/2)
        self.nodes[name] = (x,y,w,h,shape)

    def point(self,name,side):
        x,y,w,h,_ = self.nodes[name]
        return {'n':(x,y+h/2),'s':(x,y-h/2),'e':(x+w/2,y),
                'w':(x-w/2,y),'nw':(x-w/2,y+h/2),
                'ne':(x+w/2,y+h/2),'c':(x,y)}[side]

    def line(self,points,dashed=False):
        xs,ys=zip(*points)
        self.ax.plot(xs,ys,color='black',linewidth=.55,
                     linestyle=(0,(4,3)) if dashed else 'solid',zorder=1)

    def arrow(self,p,q,dashed=False,via=()):
        points=[p,*via,q]
        if via:self.line(points[:-1],dashed)
        self.ax.add_patch(FancyArrowPatch(points[-2],points[-1],
                         arrowstyle='-|>',mutation_scale=7.5,linewidth=.55,
                         color='black',shrinkA=0,shrinkB=0,
                         linestyle=(0,(4,3)) if dashed else 'solid',zorder=1))

    def edge(self,a,b,sa='s',sb='n',**kwargs):
        self.arrow(self.point(a,sa),self.point(b,sb),**kwargs)

    def frame(self,x,y,w,h):
        self.ax.add_patch(Rectangle((x,y),w,h,fill=False,edgecolor='black',
                                   linewidth=.55,linestyle=(0,(4,3)),zorder=0))

    def save(self,out,name):
        # Fixed physical canvas: do not enlarge or rasterize the scientific figure.
        self.fig.canvas.draw()
        renderer=self.fig.canvas.get_renderer()
        x0,x1=self.ax.get_xlim();y0,y1=self.ax.get_ylim()
        for artist,node in self.labels:
            b=artist.get_window_extent(renderer).transformed(self.ax.transData.inverted())
            if b.x0<x0-.02 or b.x1>x1+.02 or b.y0<y0-.02 or b.y1>y1+.02:
                raise ValueError(name+': clipped label '+repr(artist.get_text()))
            if node and (b.x0<node[0]-.02 or b.x1>node[2]+.02 or b.y0<node[1]-.02 or b.y1>node[3]+.02):
                raise ValueError(name+': label exceeds node '+repr(artist.get_text()))
        self.fig.savefig(out/(name+'.pdf'),format='pdf',
                         metadata={'Creator':'Python Matplotlib','Producer':None,
                                   'CreationDate':None,'ModDate':None})
        plt.close(self.fig)

def render(out):
    d=Drawing((0,0,16.8,7.7))
    for name,x,y,w,label,dash in [('decl',2.5,5.15,4.4,'Finite drift contract\nschemas, atoms, costs, updates',False),('compile',8.4,5.15,4.4,'Enumerating compiler\ntotal transition tables',False),('reach',14.1,5.15,4.6,'Reachable joint states\nfuture equivalence',False),('basis',14.1,2.8,4.6,'Minimal separator\nobstruction basis',False),('solve',8.4,2.8,4.4,'Exact weighted\nhitting-set solver',False),('out',2.5,2.8,4.4,'Optimal portfolio\nor replayable impossibility',False),('ref',8.4,7,4.4,'Independent primitive interpreter',True),('checker',14.1,.75,4.6,'Independent safety and\ncertificate checker',True)]:
        d.box(name,x,y,w,1,label,dashed=dash,size=8.5)
    for a,b,sa,sb in [('decl','compile','e','w'),('compile','reach','e','w'),('reach','basis','s','n'),('basis','solve','w','e'),('solve','out','w','e')]:d.edge(a,b,sa,sb)
    d.edge('ref','compile',dashed=True);d.edge('checker','basis','n','s',dashed=True)
    d.edge('checker','out','w','s',dashed=True,via=((2.5,.75),))
    d.save(out,'workflow')
    d=Drawing((0,0,8.6,6.6))
    for name,x,label in [('h1',2.1,r'$h_1:(0,0),(1,1)$'),('h2',6.5,r'$h_2:(0,1),(1,0)$')]:d.box(name,x,5.8,3,.7,label,size=8.5)
    for n,x,label in [('s1',2.1,r'$\sigma$'),('s2',6.5,r'$\sigma$'),('q1',2.1,r'$q(h_1)$'),('q2',6.5,r'$q(h_2)$')]:
        d.box(n,x,3.8 if n[0]=='s' else 1.8,1.1,.8,label,shape='circle',size=8.5)
    d.edge('h1','s1');d.edge('h2','s2')
    d.text(2.85,4.8,'selected\nmarginals',size=8);d.text(7.25,4.8,'selected\nmarginals',size=8)
    d.line([d.point('s1','e'),d.point('s2','w')],dashed=True)
    d.text(4.3,4.15,'equal retained state',size=8.5)
    d.edge('h1','q1','w','w',via=((.5,5.8),(.5,1.8)))
    d.edge('h2','q2','e','e',via=((8.1,5.8),(8.1,1.8)))
    d.text(.18,3.8,'full-history replay',size=8).set_rotation(90)
    d.text(8.4,3.8,'full-history replay',size=8).set_rotation(90)
    for name,x,label in [('q1',2.1,'$o=0$'),('q2',6.5,'$o=1$')]:
        d.arrow(d.point(name,'s'),(x,.95));d.text(x,.65,label)
    d.text(4.3,.25,r'$\Delta(h_1,h_2)=\varnothing$',size=9)
    h1=[(0,0),(1,1)];h2=[(0,1),(1,0)]
    marginal=lambda h:(sum(a for a,b in h),sum(b for a,b in h),len(h))
    if marginal(h1)!=marginal(h2) or [sum(a!=b for a,b in h) for h in [h1,h2]]!=[0,2]:raise ValueError('Zero-separator example changed')
    d.save(out,'obstruction')

def main():
    import tempfile
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--check',action='store_true')
    a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True);render(a.output_dir)
    if a.check:
        with tempfile.TemporaryDirectory() as one,tempfile.TemporaryDirectory() as two:
            render(Path(one));render(Path(two))
            for name in ['workflow','obstruction']:
                if (Path(one)/(name+'.pdf')).read_bytes()!=(Path(two)/(name+'.pdf')).read_bytes():raise ValueError('Fresh exports differ: '+name)
    print('Two drift-contract vector diagrams and marginal obstruction checked.')

if __name__=='__main__':main()

