"""
	An exporter that writes gcode files.
	Most of the intelligence of following paths is available in PathExport.
	
	This simply translates ArcMove and LinearMove objects into Gcode syntax
"""
import os,sys,logging
from OCC import gp;

import PathExport
import SlicerConfig
import TestDisplay
import Wrappers
log = logging.getLogger('GcodeExporter');

"""
	Exports gcode for a list of shapes.
	PathExporter has already handled translating curves,
	catching naive moves, etc-- this class simply translates
	to Gcode syntax.
	
	The primary difference is the addition of feedrates, 
	as well as suppressing consecutive dims that are the same
	
	The interface is designed to do stream-based conversion, so that
	all of the commands are not required to be in memory at the same time.
	
	NOTE: the machine starts with position [0,0,0].
	
	TODO: add 4th dimension for extruder control
"""
class GcodeExporter:
	def __init__(self,options):
	
		#defines the initial machine coordinates
		#and tracks current position for incremental coordinates
		self.currentPosition = gp.gp_Pnt(-999,-999,-999);
		self.incremental = False;
		self.lastMove = None;
		self.options=options;
		
	def export(self, fileName,slicer):
		"export gcode for the completed slicer"
		
		f= open ( fileName ,'w');
		
		for c in self.header():
			f.write(c);

		for s in slicer.slices:
			f.write(self.comment("Slice zLevel %0.3f" % s.zLevel ));
			log.warn("Slice zLevel %0.3f" % s.zLevel );
			f.write(self.comment("FillWires") + "\n");
		

			for gc in self.gcode(s.fillWires):
				f.write(gc);
				
			f.write(self.comment("InfillEdges")  + "\n");
			for gc in self.gcode(s.fillEdges):
				f.write(gc);
		
		f.close();
	
	def header(self):
		"generator that returns the required header"
		if self.incremental:
			yield "G91";
			yield self.comment( "Incremental Distance Mode.");
		else:
			yield "G90";
			yield self.comment( "Absolute Distance Mode.");
		yield "F" + self.options.numberFormat % self.options.feedRate;
		
	def gcode(self,shapeList):
		"convert the list of shapes to gcode"
		"returns a generator of gcode lines"
		"listOfShape is a list of wires, edges, or compounds of these"
				
		pe = PathExport.ShapeDraw(self.options.useArcs,self.options.curveApproximationTolerance);
			
		for move in pe.follow(shapeList):
			log.debug( move );
			cmd = [];
			moveType = move.__class__.__name__;
			
			#regardless of whether we're doing an arc or linear move,
			#we'll need to know the end X, Y, and Z values
			if self.incremental:
				compareVals = [ 0, 0 , 0];
				moveVals = move.distance();
			else:
				compareVals = [ self.currentPosition.X(), self.currentPosition.Y(), self.currentPosition.Z() ];
				moveVals = move.vector();
			log.debug("CompareVals" + str(compareVals));
			log.debug("MoveVals" + str(moveVals));
			c = self._appendAxisValues(compareVals,moveVals);
			log.debug("Computed Move" + str(c) );
			if moveType == "LinearMove":
				if len(c) > 0:
					if move.draw:
						cmd.append("G01");
					else:
						cmd.append("G00");					
					cmd.extend ( c);
					

			elif moveType == "ArcMove" :
				"it is an arc move"
				if move.ccw:
					cmd.append("G03");
				else:
					cmd.append("G02");
				#I and J are always relative to the start point. of the arc. but
				#X, Y, and Z have to honor incremental or absolute mode
				i = move.centerPoint.X() - move.fromPoint.X();
				j = move.centerPoint.Y() - move.fromPoint.Y();
				cmd.append("I" + self.options.numberFormat % i );
				cmd.append("J" + self.options.numberFormat % j);
				cmd.extend(c);
			
			else:
				cmd.append("Unknown Move Type" + moveType);
			
			if self.options.computeExtraAxis and len(cmd) > 0 :
				cmd.append(self.options.extraAxisName + (self.options.numberFormat % move.length()) );

			if len(cmd)> 0:
				yield " ".join(cmd) + "\n";
			
			self.lastMove = move;
			self.currentPosition = move.toPoint;
			log.debug("CurrentPosition = " + str(Wrappers.Point(self.currentPosition)));			
			
	
	def _appendAxisValues(self,compareValues, moveValues):
		"appends Axis Values based on whether they are needed or not"
		"returns an array of move Values"
		cmd = [];
		m = map(self._withinTolerance,compareValues, moveValues);
		#log.debug("Mapped Values:"+ str(m));
		if m[0] != None:
			cmd.append("X" + self.options.numberFormat % m[0] );
		if m[1] != None:
			cmd.append("Y" + self.options.numberFormat % m[1] );
		if m[2] != None:
			cmd.append("Z" + self.options.numberFormat % m[2] );
		
		return cmd;
		
	def _withinTolerance(self,refVal, theVal):
		"returns theVal if the two are not the same, otherwise returns None"
		if refVal != None and theVal != None:			
			#if  abs(refVal - theVal) <= self.options.machineResolution:
			if abs(refVal - theVal ) <= 0.000001:
				return None;
		
		return theVal;

	def comment(self,txt):
		return self.options.commentFormat  % txt;
		
if __name__=='__main__':

	###Logging Configuration
	logging.basicConfig(level=logging.WARN,
						format='%(asctime)s [%(funcName)s] %(levelname)s %(message)s',
						stream=sys.stdout)	
						
	w1 = TestDisplay.makeSquareWire();
	w2 = TestDisplay.makeCircleWire();
	w3 = TestDisplay.makeReversedWire();
	TestDisplay.display.showShape([w1,w2,w3]);
	o = SlicerConfig.GcodeOptions();
	o.setDefaults();
	o.computeExtraAxis=False;
	ge = GcodeExporter(o );
	#ge.useArcs = False;
	for line in ge.gcode([w1,w2,w3]):
		print line,;

		
	TestDisplay.display.run();