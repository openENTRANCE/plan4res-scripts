#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Import packages
import pyam
import pandas as pd ## necessary data analysis package
import numpy as np
import os
import yaml
import calendar
from math import ceil
from datetime import timedelta
from calendar import monthrange
from itertools import product

cfg={}
# open the configuration file using the pathway defined below
with open("settingsCreateInputPlan4res.yml","r") as mysettings:
	cfg=yaml.load(mysettings,Loader=yaml.FullLoader)
	
isInertia= ( 'Inertia' in cfg['Parameters']['CouplingConstraints'] )
isPrimary= ( 'Primary' in cfg['Parameters']['CouplingConstraints'] )
isSecondary= ( 'Secondary' in cfg['Parameters']['CouplingConstraints'] )
isCO2= ( 'CO2' in cfg['Parameters']['CouplingConstraints'] )
partitionDemand = cfg['Parameters']['CouplingConstraints']['Demand']['Partition']
if isInertia: partitionInertia=cfg['Parameters']['CouplingConstraints']['Inertia']['Partition']
if isPrimary: partitionPrimary=cfg['Parameters']['CouplingConstraints']['Primary']['Partition']
if isSecondary: partitionSecondary=cfg['Parameters']['CouplingConstraints']['Secondary']['Partition']
isInvest= ('CapacityExpansion' in cfg['Parameters'])

# connect to the openentrance scenario explorer (set credentials)
if cfg['mode_annual']=='platform' or cfg['mode_subannual']=='platform':
	pyam.iiasa.set_config(cfg['user'],cfg['password'])
	pyam.iiasa.Connection('openentrance')

# create the dictionnary of variables containing the correspondence between plan4res (SMS++) variable 
# names and openentrance nomenclature variable names
vardict={}
with open("VariablesDictionnary.yml","r") as myvardict:
	vardict=yaml.safe_load(myvardict)

# create the dictionnary of time series, containing the names of the timeseries to be included in 
# the dataset
timeseriesdict={}
with open("DictTimeSeries.yml","r") as mytimeseries:
	timeseriesdict=yaml.safe_load(mytimeseries)

# if only one scenario/year is defined in config file set the list of scenarios / years to 1 element
if 'scenarios' not in cfg: cfg['scenarios']= [ cfg['scenario'] ]
if 'years' not in cfg: cfg['years']= [ cfg['year'] ]

# create the list of options
if 'options' in cfg: 
	option_types=cfg['options']
	cfg['options']=[]
	for option_type in option_types:
		cfg['options'].append('WITH_'+option_type)
		cfg['options'].append('WITHOUT_'+option_type)
else: cfg['options']=['None']

cfg['UCScenarios']=[str(x) for x in cfg['UCScenarios']]

# loop on scenarios, years, options => create one dataset per (scenario,year,option) triplet
for current_scenario, current_year, current_option in product(cfg['scenarios'],cfg['years'],cfg['options']):
	cfg['scenario']=current_scenario
	cfg['year']=current_year
	print('create dataset for ',current_scenario,', ',current_year, ' and ',current_option)
	if not current_option=='None':
		outputdir=cfg['outputpath']+'plan4res-'+cfg['scenario']+'-'+str(cfg['year'])+'-'+current_option
		if not os.path.isdir(outputdir):os.mkdir(outputdir)
	else:
		outputdir=cfg['outputpath']+'plan4res-'+cfg['scenario']+'-'+str(cfg['year'])
		if not os.path.isdir(outputdir):os.mkdir(outputdir)
	outputdir=outputdir+'/'

	timestepduration=cfg['TimeStep']['number']										 

	# upload of relevant Scenario data from platform
	# creation of a csv file and a pandas dataframe containing all necessary data
	####################################################################################################
	i=0

	ExistsAnnualData=False  # AnnualDataFrame is still empty
	ExistsSubAnnualData=False # SubAnnualDataFrame is still empty
	SubAnnualDataFrame=pyam.IamDataFrame
	AnnualDataFrame=pyam.IamDataFrame

	listLocalReg=[]
	listGlobalReg=[]

	# define list of aggregated regions
	with open(cfg['nomenclatureDir']+"region/nuts3.yaml","r",encoding='UTF-8') as nutsreg:
		nuts3=yaml.safe_load(nutsreg)
	with open(cfg['nomenclatureDir']+"region/nuts2.yaml","r",encoding='UTF-8') as nutsreg:
		nuts2=yaml.safe_load(nutsreg)
	with open(cfg['nomenclatureDir']+"region/nuts1.yaml","r",encoding='UTF-8') as nutsreg:
		nuts1=yaml.safe_load(nutsreg)
	with open(cfg['nomenclatureDir']+"region/countries.yaml","r",encoding='UTF-8') as nutsreg:
		countries=yaml.safe_load(nutsreg)
	with open(cfg['nomenclatureDir']+"region/ehighway.yaml","r",encoding='UTF-8') as nutsreg:
		subcountries=yaml.safe_load(nutsreg)
	with open(cfg['nomenclatureDir']+"region/european-regions.yaml","r",encoding='UTF-8') as nutsreg:
		aggregateregions=yaml.safe_load(nutsreg)

	# create table of correspondence for iso3 and iso2 names
	iso3=pd.Series(str)
	iso2=pd.Series(str)
	listcountries=[]
	for k in range(len(countries[0]['Countries'])):
		countryname=next(iter(countries[0]['Countries'][k]))
		iso=countries[0]['Countries'][k][countryname]['iso3']
		iso3[iso]=countryname
		iso=countries[0]['Countries'][k][countryname]['iso2']
		iso2[iso]=countryname
		listcountries.append(countryname)
	dict_iso3=iso3.to_dict()
	dict_iso2=iso2.to_dict()
	rev_dict_iso3={v:k for k,v in dict_iso3.items()}
	rev_dict_iso2={v:k for k,v in dict_iso2.items()}

	# create the list of regions to work on 
	for datagroup in cfg['listdatagroups']:
		if type(cfg['datagroups'][datagroup]['regions']['local'])==list: listLocalReg=listLocalReg+cfg['datagroups'][datagroup]['regions']['local']
		elif cfg['datagroups'][datagroup]['regions']['local']=='countries':listLocalReg=listLocalReg+countries.keys()
		elif cfg['datagroups'][datagroup]['regions']['local']=='countries_ISO3':listLocalReg=listLocalReg+iso3.index.tolist()
		elif cfg['datagroups'][datagroup]['regions']['local']=='countries_ISO2':listLocalReg=listLocalReg+iso2.index.tolist()
		
		if(cfg['datagroups'][datagroup]['regions']['global']): listGlobalReg.append(cfg['datagroups'][datagroup]['regions']['global'])
		
	if cfg['mode_annual']!='fulldata' or cfg['mode_subannual']!='fulldata':
	# case where data are retrieved from openentrance datafiles (upoaded from scenario explorer) or directly on the scenario explorer	

		# create list of lines
		lines=[]
		for region1 in cfg['listregionsGET']:
			for region2 in cfg['listregionsGET']:
				if (region1!=region2):
					lines.append(region1+'>'+region2)
					lines.append(region2+'>'+region1)
		
		# define list of regions including lines
		listLocalReg=listLocalReg+lines  
		for region in cfg['listregionsGET']:
			if region not in listGlobalReg: listLocalReg.append(region)
		listRegGet=listLocalReg+listGlobalReg
		
		# treat cases where disaggregation level is nuts1/2/3
		minaggr=''
		nuts3list= {}
		nuts2list= {}
		nuts1list= {}
		for k in nuts1[0]['NUTS1']: nuts1list.update(k)
		for k in nuts2[0]['NUTS2']: nuts2list.update(k)
		for k in nuts3[0]['NUTS3']: nuts3list.update(k)
		# create lists of nuts per countries
		countryNuts3={v:[] for v in listcountries}
		{countryNuts3[v['country']].append(k) for k,v in nuts3list.items()}
		countryNuts2={v:[] for v in listcountries}
		{countryNuts2[v['country']].append(k) for k,v in nuts2list.items()}
		countryNuts1={v:[] for v in listcountries}
		{countryNuts1[v['country']].append(k) for k,v in nuts1list.items()}
		
		# extend list of regions to get with regions from datagroups
		if 'nuts3' in listRegGet:
			while 'nuts3' in listRegGet: listRegGet.remove('nuts3')
			listRegGet=listRegGet+list(nuts3.keys())
			minaggr='nuts3'	
		if 'nuts2' in listRegGet:
			while 'nuts2' in listRegGet: listRegGet.remove('nuts2')
			listRegGet=listRegGet+list(nuts2.keys())
			minaggr='nuts2'	
		if 'nuts1' in listRegGet:
			while 'nuts1' in listRegGet: listRegGet.remove('nuts1')
			listRegGet=listRegGet+list(nuts1.keys())
			minaggr='nuts1'	
		if 'countries' in listRegGet:
			while 'countries' in listRegGet: listRegGet.remove('countries')
			listRegGet=listRegGet+list(countries.keys())

		# create list of variables
		for datagroup in cfg['listdatagroups']:
		# loop on all different data sources
			if 'scenario' in cfg['datagroups'][datagroup]: scenget=cfg['datagroups'][datagroup]['scenario']
			else: scenget=cfg['scenario']
			print('reading '+datagroup)
			
			listvardatagroup=[]
			listlocalvar=[] # list of variables which are not 'global'
			listglobalvar=[]
			globalreg= cfg['datagroups'][datagroup]['regions']['global']
			
			# loop on category of variables : coupling or techno
			for varcat1 in cfg['datagroups'][datagroup]['listvariables']:
				# treat coupling variables (ie variables not depending on techno)
				if varcat1=='coupling':
					# loop on category of coupling variables: mean, add, flow or global
					for varcat2 in cfg['datagroups'][datagroup]['listvariables'][varcat1].keys():
						# loop on variables
						for var in cfg['datagroups'][datagroup]['listvariables'][varcat1][varcat2]:
							listvardatagroup.append(var)
						# specific treatment for global variables (meaning they do not depend on regions)
							if varcat2=='global':listglobalvar.append(var)
							else: listlocalvar.append(var)
								
				# treat variables depending on technos
				elif varcat1=='techno':
					# loop on category of techno variables: thermal, reservoir, .....
					for varcat2 in cfg['datagroups'][datagroup]['listvariables'][varcat1].keys():
						# loop on category of variables: add, mean, global
						for varcat3 in cfg['datagroups'][datagroup]['listvariables'][varcat1][varcat2].keys():
							# is there only a list of variables or subgroups of variables per fuels
							if(type(cfg['datagroups'][datagroup]['listvariables'][varcat1][varcat2][varcat3])==list):
								# loop on variables and fuels
								for var in cfg['datagroups'][datagroup]['listvariables'][varcat1][varcat2][varcat3]:
									for fuel in cfg['technos'][varcat2]:
										newvar=var+fuel
										listvardatagroup.append(newvar)
										if varcat3=='global': listglobalvar.append(newvar) 
										else: listlocalvar.append(newvar)
							else: # there are subgroups of variables per fuels
								for subgroup in cfg['datagroups'][datagroup]['listvariables'][varcat1][varcat2][varcat3].keys():
									for var in cfg['datagroups'][datagroup]['listvariables'][varcat1][varcat2][varcat3][subgroup]['variables']:
										for fuel in cfg['datagroups'][datagroup]['listvariables'][varcat1][varcat2][varcat3][subgroup]['fuels']:
											newvar=var+fuel
											listvardatagroup.append(newvar)
											if varcat3=='global': listglobalvar.append(newvar) 
											else: listlocalvar.append(newvar)
			
			if ( cfg['datagroups'][datagroup]['subannual'] and cfg['mode_subannual']=='platform') or ( not cfg['datagroups'][datagroup]['subannual'] and cfg['mode_annual']=='platform'):
				print('download data from platform')
				
				groupdf=pyam.read_iiasa('openentrance',model=cfg['datagroups'][datagroup]['model'],
					variable=listvardatagroup,
					region=listRegGet,year=cfg['year'],
					scenario=scenget)
				
				# remove rows for global variables / local regions or local variables / global regions
				groupdf=groupdf.filter(region=globalreg, variable=listlocalvar, keep=False)
				groupdf=groupdf.filter(region=listLocalReg, variable=listglobalvar, keep=False)
				
				# rename regions if necessary
				if cfg['datagroups'][datagroup]['regions']['local']=='countries_ISO3':groupdf.rename(dict_iso3,inplace=True)
				if cfg['datagroups'][datagroup]['regions']['local']=='countries_ISO2':groupdf.rename(dict_iso2,inplace=True)

				if cfg['datagroups'][datagroup]['subannual']:
					if not ExistsSubAnnualData:
						ExistsSubAnnualData=True
						SubAnnualDataFrame=groupdf
					else:
						SubAnnualDataFrame=SubAnnualDataFrame.append(groupdf)
				else:
					if not ExistsAnnualData:
						ExistsAnnualData=True
						AnnualDataFrame=groupdf
					else:
						AnnualDataFrame=AnnualDataFrame.append(groupdf)
					
			if not (cfg['mode_annual']=='platform' and cfg['mode_subannual']=='platform'):
				# load data from files per data source (previously uploaded from platform)
				print('open data files')
			
				if ( cfg['datagroups'][datagroup]['subannual'] and cfg['mode_subannual']=='files') or ( not cfg['datagroups'][datagroup]['subannual'] and cfg['mode_annual']=='files'):
					print('reading '+datagroup)
															
					if 'Start' in cfg['datagroups'][datagroup]['inputdata']:
						file=cfg['datagroups'][datagroup]['inputdatapath']+cfg['datagroups'][datagroup]['inputdata']['Start']+str(cfg['variant']) +cfg['datagroups'][datagroup]['inputdata']['End']
					else:
						file=cfg['datagroups'][datagroup]['inputdatapath']+cfg['datagroups'][datagroup]['inputdata']
					print('read file '+file)
					
					# creation of empty df for storing annual and subannual data for the current group
					dfdatagroup=pyam.IamDataFrame(pd.DataFrame(columns=['model','scenario','region','variable','unit','subannual',str(cfg['year'])]))
					# filter on the listgetfegion regions
					SubAdfdatagroup=pyam.IamDataFrame(pd.DataFrame(columns=['model','scenario','region','variable','unit','subannual',str(cfg['year'])]))
					
					# read data as a IAMDataFrame
					print('read as df')
					if 'xlsx' in file:
						df=pd.read_excel(file,sheet_name='data')
					else:
						df=pd.read_csv(file)
					
					if 'Subannual' in df.columns:
						if len(df['Subannual'].unique()==1): df=df.drop(['Subannual'],axis=1)
					dfdatagroup=pyam.IamDataFrame(data=df)

					if 'countries_ISO3' in cfg['datagroups'][datagroup]['regions']['local']:
						print('renaming ISO3')
						dfdatagroup=dfdatagroup.rename(region=dict_iso3)
					if 'countries_ISO2' in cfg['datagroups'][datagroup]['regions']['local']:
						print('renaming ISO2')
						dfdatagroup=dfdatagroup.rename(region=dict_iso2)
					
					print('change country names')
					dfdatagroup=dfdatagroup.filter(region=listRegGet)
					
					print('filter countries')
					# if there are data at lower granularity than country or cluster (only country until now), aggregate
					firstcountry=1
					for country in listcountries:
						
						# create list of nuts of the country
						listNuts1=countryNuts1[country]
						listNuts2=countryNuts2[country]
						listNuts3=countryNuts3[country]
						listNuts=listNuts1+listNuts2+listNuts3
						NumberOfNutsLists=int(len(listNuts1)>0)+int(len(listNuts2)>0)+int(len(listNuts3)>0)
						# To be implemented: include weights to aggregation, weight=1/NumberOfNutsLists
						
						if (len(listNuts)>0 and ('NoNutsAggregation' not in cfg)): 
							print('aggregating nuts')
							dfdatagroup.aggregate_region(dfdatagroup.variable,region=country, subregions=listNuts, append=True)

					dfdatagroup=dfdatagroup.filter(model=cfg['datagroups'][datagroup]['model'])
					dfdatagroup=dfdatagroup.filter(scenario=scenget)
					dfdatagroup=dfdatagroup.filter(year=cfg['year'])
					dfdatagroup=dfdatagroup.filter(variable=listvardatagroup)
					# remove local variables on global region and global variables on local regions
					dfdatagroup=dfdatagroup.filter(region=globalreg, variable=listlocalvar, keep=False)
					dfdatagroup=dfdatagroup.filter(region=listLocalReg, variable=listglobalvar, keep=False)
					if cfg['datagroups'][datagroup]['subannual']: SubAdfdatagroup=dfdatagroup
					
					if cfg['datagroups'][datagroup]['subannual']:
						if not ExistsSubAnnualData:
							ExistsSubAnnualData=True
							SubAnnualDataFrame=SubAdfdatagroup
						else:
							SubAnnualDataFrame=SubAnnualDataFrame.append(SubAdfdatagroup)
					else:
						if not ExistsAnnualData:
							ExistsAnnualData=True
							AnnualDataFrame=dfdatagroup
						else:
							AnnualDataFrame=AnnualDataFrame.append(dfdatagroup)
		
		#conversion of units to plan4res usual units (MWh, MW, €/MWh, €/MW/yr, €/MW)
		if(ExistsAnnualData): #check if there exist annual data
			print('converting units')
			for var_unit in cfg['Parameters']['conversions']:
				if 'factor' in cfg['Parameters']['conversions'][var_unit]:
					AnnualDataFrame=AnnualDataFrame.convert_unit(var_unit, to=cfg['Parameters']['conversions'][var_unit]['to'], factor=float(cfg['Parameters']['conversions'][var_unit]['factor'])) 
				else:
					AnnualDataFrame=AnnualDataFrame.convert_unit(var_unit, to=cfg['Parameters']['conversions'][var_unit]['to']) 

			# validate the format of the data (prevents errors)
			AnnualDataFrame.validate(exclude_on_fail=True)
		
		if(ExistsSubAnnualData): # check if there exist subannual data
			for var_unit in cfg['Parameters']['conversions']:
				if 'factor' in cfg['Parameters']['conversions'][var_unit]:
					SubAnnualDataFrame=SubAnnualDataFrame.convert_unit(var_unit, to=cfg['Parameters']['conversions'][var_unit]['to'], factor=cfg['Parameters']['conversions'][var_unit]['factor']) 
				else:
					SubAnnualDataFrame=SubAnnualDataFrame.convert_unit(var_unit, to=cfg['Parameters']['conversions'][var_unit]['to']) 

			SubAnnualDataFrame.validate(exclude_on_fail=True)
			SubAnnualDataFrame.to_csv('mySubAdf.csv')
			
		#regional aggregations 
		print('computing regional aggregations')
		
		# some variables are added (all energy, capacity), others are averageded, and finally for flow variable specific aggregations are done
		listvaradd=[]
		listvarmean=[]
		for datagroup in cfg['listdatagroups']:
			if 'coupling' in cfg['datagroups'][datagroup]['listvariables'].keys():
				for typeagr in cfg['datagroups'][datagroup]['listvariables']['coupling'].keys():
					for var in cfg['datagroups'][datagroup]['listvariables']['coupling'][typeagr]:
						variable=var
						if typeagr=='add': 
							if variable not in listvaradd: 
								listvaradd.append(variable)
						elif typeagr=='mean': 
							if variable not in listvarmean: 
								listvarmean.append(variable)
			if 'techno' in cfg['datagroups'][datagroup]['listvariables'].keys():
				for technogroup in cfg['datagroups'][datagroup]['listvariables']['techno'].keys():
					for typeagr in cfg['datagroups'][datagroup]['listvariables']['techno'][technogroup].keys():
						if type(cfg['datagroups'][datagroup]['listvariables']['techno'][technogroup][typeagr])==list:
							for var in cfg['datagroups'][datagroup]['listvariables']['techno'][technogroup][typeagr]:
								for techno in cfg['technos'][technogroup]:
									newvar=var+techno
									if typeagr=='add': 
										if newvar not in listvaradd: 
											listvaradd.append(newvar)
									elif typeagr=='mean': 
										if newvar not in listvarmean: 
											listvarmean.append(newvar)
						else:
							for groupvar in cfg['datagroups'][datagroup]['listvariables']['techno'][technogroup][typeagr].keys():
								for fuel in cfg['datagroups'][datagroup]['listvariables']['techno'][technogroup][typeagr][groupvar]['fuels']:
									for var in cfg['datagroups'][datagroup]['listvariables']['techno'][technogroup][typeagr][groupvar]['variables']:
										newvar=var+fuel
										if typeagr=='add': 
											if newvar not in listvaradd: 
												listvaradd.append(newvar)
										elif typeagr=='mean': 
											if newvar not in listvarmean: 
												listvarmean.append(newvar)

		if(cfg['aggregateregions']):
			for reg in cfg['aggregateregions'].keys():
				print('aggregating ' +reg)
				# creation of aggregated timeseries
				listTypes={'ZV': cfg['ActivePowerDemand'],'RES':cfg['technos']['res']+cfg['technos']['runofriver'],'SS':['Inflows']}
				for typeData in listTypes:
					for typeSerie in listTypes[typeData]:
						sumValTS=0.0
						firstSerie=True
						isSeries=False
						for region in cfg['aggregateregions'][reg]:
							if region in timeseriesdict[typeData][typeSerie].keys():
								isSeries=True
								timeserie=pd.read_csv(cfg['dirTimeSeries']+timeseriesdict[typeData][typeSerie][region],index_col=0,skiprows=1)
								if len(timeserie.columns)>1:
									for col in timeserie.columns:
										if 'Unnamed' in col: timeserie.drop([col],axis=1)
									timeserie=timeserie[ cfg['UCScenarios'] ]
								else:
									timeserie.columns=['DET']
								if typeData=='ZV':
									varTS=vardict['Input']['Var'+typeData][typeSerie]
								elif typeData=='SS':
									varTS=vardict['Input']['Var'+typeData][typeSerie]+'Reservoir'
								else:
									varTS=vardict['Input']['Var'+typeData]['MaxPower']+typeSerie
								if varTS in AnnualDataFrame.variable:
									valTS_IAMdf=AnnualDataFrame.filter(variable=varTS,region=region,year=current_year).as_pandas()['value'].unique()
									if len(valTS_IAMdf)>0: valTS=valTS_IAMdf[0]
									else: valTS=0.0
								else:
									# the only variables which may not be in the data are the different parts of the ActiveDemand:
									if varTS in [timeseriesdict['ZV'][part] for part in cfg['ActivePowerDemand']]:
										# compute valTS as Total-sum of parts which are present
										valTS=AnnualDataFrame[ (AnnualDataFrame['Variable']==timeseriesdict['ZV']['Total']) & (df['Region']==region) ][str(current_year)].unique()[0]
										for part in cfg['ActivePowerDemand']:
											if vardict['Input']['Var'+typeData][part] in AnnualDataFrame['Variable'].unique():
												valTS=valTS-AnnualDataFrame[ (AnnualDataFrame['Variable']==timeseriesdict['ZV'][part]) & (df['Region']==region) ][str(current_year)].unique()[0]
								if valTS==0.0: valTS=cfg['Parameters']['zerocapacity'] 
								if firstSerie: 
									newSerie=valTS*timeserie
									firstSerie=False
									sumValTS=valTS
								else:
									newSerie=newSerie+valTS*timeserie
									sumValTS=sumValTS+valTS
						if isSeries:
							if sumValTS>0: newSerie=(1/sumValTS)*newSerie
							else: newSerie=0.0*newSerie
							nameNewSerie='AggregatedTimeSerie_'+typeSerie+'_'+reg+'.csv'
							newSerie.to_csv(cfg['dirTimeSeries']+nameNewSerie)
							timeseriesdict[typeData][typeSerie][reg]=nameNewSerie
			
				# aggregation of variables
				for variable in listvaradd:
					if ExistsAnnualData: 
						if variable in AnnualDataFrame.variable: AnnualDataFrame.aggregate_region(variable, region=reg, subregions=cfg['aggregateregions'][reg], append=True)
					if ExistsSubAnnualData: 
						if variable in SubAnnualDataFrame.variable: SubAnnualDataFrame.aggregate_region(variable, region=reg, subregions=cfg['aggregateregions'][reg], append=True)
				for variable in listvarmean:
					if ExistsAnnualData: 
						if variable in AnnualDataFrame.variable: AnnualDataFrame.aggregate_region(variable, region=reg, subregions=cfg['aggregateregions'][reg], method='mean',append=True)	
					if ExistsSubAnnualData: 
						if variable in SubAnnualDataFrame.variable: SubAnnualDataFrame.aggregate_region(variable, region=reg, subregions=cfg['aggregateregions'][reg], method='mean',append=True)	
		#remove aggregated subregions
		listregion=listGlobalReg
		for partition in cfg['partition']:
			for region in cfg['partition'][partition]:
				if region not in listregion: listregion.append(region)

		if ExistsAnnualData: 
			AnnualDataFrame=AnnualDataFrame.filter(region=(listregion+lines))
			AnnualDataFrame.to_csv(outputdir+'IAMC_annual_data.csv')
			bigdata=AnnualDataFrame
		if ExistsSubAnnualData: 
			SubAnnualDataFrame=SubAnnualDataFrame.filter(region=(listregion+lines))
			SubAnnualDataFrame.to_csv(outputdir+'IAMC_subannual_data.csv')
			bigdata_SubAnnual=SubAnnualDataFrame
		

	if cfg['mode_annual']=='fulldata': bigdata=pyam.IamDataFrame(data=outputdir+'IAMC_annual_data.csv')
	if cfg['mode_subannual']=='fulldata':bigdata_SubAnnual=pyam.IamDataFrame(data=outputdir+'IAMC_subannual_data.csv')
			
	# creation of plan4res dataset
	################################"

	# creating list of regions
	listregions=listGlobalReg
	for partition in list(cfg['partition'].keys()):
		listregions=listregions+cfg['partition'][partition]
	listregions = list(set(listregions))
	print('regions in dataset:')
	print(listregions)

	# create file ZP_ZonePartition
	#############################################################
	if cfg['treat']['ZP']:
		print('Treating ZonePartition')
		#dictzone = dict(zip(paramZone['Name'], paramZone['Partition']))
		nbreg=len(cfg['partition'][ partitionDemand  ])
		nbpartition=len(cfg['partition'])

		ZP = pd.DataFrame(columns=list(cfg['partition'].keys()),index=range(nbreg))
		ZP[ partitionDemand ]=pd.Series(cfg['partition'][ partitionDemand ],name=partition,index=range(nbreg))
		for partition in list(cfg['partition'].keys()):
			if not partition == cfg['Parameters']['CouplingConstraints']['Demand']['Partition']:
				if len(cfg['partition'][partition])==nbreg: ZP[partition]=pd.Series(cfg['partition'][partition],name=partition,index=range(nbreg))
				else: ZP[partition]=pd.Series(cfg['partition'][partition][0] ,name=partition,index=range(nbreg))
		ZP.to_csv(outputdir+cfg['treat']['ZP'], index=False)

	# create file IN_Interconnections
	###############################################################
	if cfg['treat']['IN']:
		IN = pd.DataFrame()
		bigdata.to_csv('bigdatatest.csv')
		print('Treating Interconnections')
		for variable in vardict['Input']['VarIN']:
			varname=vardict['Input']['VarIN'][variable]
			vardf=bigdata.filter(variable=varname).as_pandas(meta_cols=False)
			vardf=vardf.set_index('region')
			vardf=vardf.rename(columns={"value":variable})
			dataIN=vardf[variable]
			IN=pd.concat([IN, dataIN], axis=1)	
		IN=IN.fillna(value=0.0)
		
		# delete lines which start/end in same aggregated
		print('deleting lines which start and end in same aggregated region')
		IN['Name']=IN.index
		IN['StartLine']=IN['Name'].str.split('>',expand=True)[0]
		IN['EndLine']=IN['Name'].str.split('>',expand=True)[1]
		IN['AgrStart']=IN['StartLine']
		IN['AgrEnd']=IN['EndLine']
		for line in dataIN.index:
			# check if start / end is in an aggregated region
			regstart=line.split('>')[0]
			regend=line.split('>')[1]
			if(cfg['aggregateregions']):
				for AggReg1 in cfg['aggregateregions'].keys():
					if (regstart in cfg['aggregateregions'][AggReg1]): IN.at[line,'AgrStart']=AggReg1
					if (regend in cfg['aggregateregions'][AggReg1]):  IN.at[line,'AgrEnd']=AggReg1
		# delete line with start and end in smae aggregated region
		DeleteLines=IN[ IN.AgrStart == IN.AgrEnd ].index
		IN=IN.drop(DeleteLines)
		
		DeleteLines=[]
		# sum lines with start in same aggregated region AND end in same other aggregated region
		print('aggregate lines which start or end in same aggregated region')
		print(cfg['aggregateregions'])
		if(cfg['aggregateregions']):
			for AggReg1 in cfg['partition'][ partitionDemand ]:
				if AggReg1 in cfg['aggregateregions'].keys(): # AggReg1 is an aggregated region
					for AggReg2 in cfg['partition'][partitionDemand]:
						if AggReg2 != AggReg1:
							if AggReg2 in cfg['aggregateregions'].keys(): # AggReg2 is another aggregated  region
								# sum all lines fitting this selection
								MaxPowerFlow=0.0
								for reg1 in cfg['aggregateregions'][AggReg1]:
									for reg2 in cfg['aggregateregions'][AggReg2]:
										if (reg1+'>'+reg2) in IN.index:
											MaxPowerFlow=MaxPowerFlow+IN['MaxPowerFlow'][reg1+'>'+reg2]
											DeleteLines.append(reg1+'>'+reg2) # delete individual line
								IN = pd.concat([IN,pd.DataFrame(data=[[MaxPowerFlow,AggReg1+'>'+AggReg2,AggReg1,AggReg2,AggReg1,AggReg2]],index=[AggReg1+'>'+AggReg2],columns=IN.columns)])
							else: 
								# AggReg2 is not an aggregated region
								MaxPowerFlow=0.0
								for reg1 in cfg['aggregateregions'][AggReg1]:
									if (reg1+'>'+AggReg2) in IN.index:
										MaxPowerFlow=MaxPowerFlow+IN['MaxPowerFlow'][reg1+'>'+AggReg2]
										DeleteLines.append(reg1+'>'+AggReg2) # delete individual line
								IN = pd.concat([IN,pd.DataFrame(data=[[MaxPowerFlow,AggReg1+'>'+AggReg2,AggReg1,AggReg2,AggReg1,AggReg2]],index=[AggReg1+'>'+AggReg2],columns=IN.columns)])
				else:
					for AggReg2 in cfg['partition'][partitionDemand]:
						if AggReg2 != AggReg1:
							if AggReg2 in cfg['aggregateregions'].keys(): # AggReg2 is an aggregated  region
								MaxPowerFlow=0.0
								for reg2 in cfg['aggregateregions'][AggReg2]:
									if (AggReg1+'>'+reg2) in IN.index:
										MaxPowerFlow=MaxPowerFlow+IN['MaxPowerFlow'][AggReg1+'>'+reg2]
										DeleteLines.append(AggReg1+'>'+reg2) # delete individual line
								IN = pd.concat([IN,pd.DataFrame(data=[[MaxPowerFlow,AggReg1+'>'+AggReg2,AggReg1,AggReg2,AggReg1,AggReg2]],index=[AggReg1+'>'+AggReg2],columns=IN.columns)])
		IN=IN.drop(DeleteLines )
		RowsToDelete = IN[ IN['MaxPowerFlow'] == 0 ].index
		IN=IN.drop(RowsToDelete )

		# merge lines reg1>reg2 reg2>reg1
		print('merging symetric lines')
		IN['MinPowerFlow']=0
		NewLines=[]
		LinesToDelete=[]
		for line in IN.index:
			regstart=line.split('>')[0]
			regend=line.split('>')[1]
			inverseline=regend+'>'+regstart
			if (line not in LinesToDelete):
				NewLines.append(line)
				LinesToDelete.append(inverseline)
				IN.at[line,'MinPowerFlow']=-1.0*IN.loc[inverseline]['MaxPowerFlow']
		IN=IN.drop(LinesToDelete)

		IN['Name']=IN.index
		IN['MaxPowerFlow']=IN['MaxPowerFlow']*timestepduration
		IN['MinPowerFlow']=IN['MinPowerFlow']*timestepduration
		
		
		listcols=['Name','StartLine','EndLine','MaxPowerFlow','MinPowerFlow']
		if 'Impedance' in IN.columns: listcols.append('Impedance')
		if isInvest and 'interconnections' in cfg['Parameters']['CapacityExpansion']:
			IN['MaxAddedCapacity']=0
			IN['MaxRetCapacity']=0
			if 'Share' in cfg['Parameters']['CapacityExpansion']['interconnections']:
				# all lines can be invested
				IN['MaxAddedCapacity']=IN['MaxPowerFlow']*cfg['Parameters']['CapacityExpansion']['interconnections']['Share']['MaxAdd']
				IN['MaxRetCapacity']=IN['MaxPowerFlow']*cfg['Parameters']['CapacityExpansion']['interconnections']['Share']['MaxRet']
			else:
				for line in cfg['Parameters']['CapacityExpansion']['interconnections']:
					if line != 'Share' and line !='InvestmentCost':
						IN.loc[line]['MaxAddedCapacity']=IN.loc[line]['MaxPowerFlow']*cfg['Parameters']['CapacityExpansion']['interconnections'][line]['MaxAdd']
						IN.loc[line]['MaxRetCapacity']=IN.loc[line]['MaxPowerFlow']*cfg['Parameters']['CapacityExpansion']['interconnections'][line]['MaxRet']
			if 'InvestmentCost' not in IN.columns:
				if 'InvestmentCost' in cfg['Parameters']['CapacityExpansion']['interconnections']:
					IN['InvestmentCost']=cfg['Parameters']['CapacityExpansion']['interconnections']['InvestmentCost']
				else:
					IN['InvestmentCost']=0
			listcols.append('MaxAddedCapacity')
			listcols.append('MaxRetCapacity')
			listcols.append('InvestmentCost')
		IN=IN[ listcols ]
		
		# delete lines which do not start and end in a zone in partition
		print('delete lines which are not in partition')
		LinesToDelete=[]
		for line in IN.index:
			regstart=line.split('>')[0]
			regend=line.split('>')[1]
			if (regstart not in listregions):
				LinesToDelete.append(line)
			if (regend not in listregions):
				LinesToDelete.append(line)
		IN=IN.drop(LinesToDelete)
		IN.to_csv(outputdir+cfg['treat']['IN'], index=False)
		
	# create file ZV_ZoneValues
	###############################################################
	numserie=0
	if cfg['treat']['ZV']:
		print('Treating ZoneValues')
		listvar=[]
		for var in vardict['Input']['VarZV'].keys(): listvar.append(vardict['Input']['VarZV'][var])
		datapartition=bigdata.filter(variable=listvar,region=listregions).as_pandas(meta_cols=False)
		datapartition=datapartition.rename(columns={"variable": "Type", "region": "Zone", "unit":"Unit"})

		# rename variables using Variables dictionnary
		# create reverse variables dictionnary
		dictZV={}
		dictZV=vardict['Input']['VarZV']
		reversedictZV={}
		for key, values in dictZV.items():
			for value in values:
				myvalue=dictZV[key]
				reversedictZV[myvalue]=key
		datapartition=datapartition.replace({"Type":reversedictZV})

		# include slack unit costs (slack means non served)
		datainertia=datapartition[ datapartition.Type == 'Inertia' ]
		Inertia=datainertia['value'].mean()
		MaxDemand=cfg['Parameters']['CouplingConstraints']['Demand']['Max']
		CostDemand=cfg['Parameters']['CouplingConstraints']['Demand']['Cost']
		MaxPrimary=cfg['Parameters']['CouplingConstraints']['Primary']['Max']
		CostPrimary=cfg['Parameters']['CouplingConstraints']['Primary']['Cost']
		MaxSecondary=cfg['Parameters']['CouplingConstraints']['Secondary']['Max']
		CostSecondary=cfg['Parameters']['CouplingConstraints']['Secondary']['Cost']
		MaxInertia=cfg['Parameters']['CouplingConstraints']['Inertia']['Max']
		CostInertia=cfg['Parameters']['CouplingConstraints']['Inertia']['Cost']
		newdata=pd.DataFrame({'Type':['Inertia','MaxInertia','CostInertia'],'Unit':['MWs/MWA','MWs/MWA','EUR/MWs/MWA'],\
				'Zone':[cfg['partition'][partitionInertia], cfg['partition'][partitionInertia], cfg['partition'][partitionInertia]],\
				'model':['Parameter','Parameter','Parameter'],\
				'scenario':[cfg['listdatagroups'][0],cfg['listdatagroups'][0],cfg['listdatagroups'][0]],\
				'value':[Inertia,MaxInertia,CostInertia],'year':[cfg['year'],cfg['year'],cfg['year']]})

		# compute missing global values
		print('compute missing Coupling constraints')
		isTotalEnergy=False
		isOtherAndCooling=False
		isNonthermo=False
		isHeat=False
		isTransport=False
		isCooling=False
		isShareCooling=False
		isElectrolyzer=False
		if 'ElecVehicle' in datapartition.Type.unique(): isTransport=True
		if 'ElecHeating'  in datapartition.Type.unique(): isHeat=True
		if 'NonThermoAndCooling' in datapartition.Type.unique(): isOtherAndCooling=True
		if 'nonthermo' in datapartition.Type.unique(): isNonthermo=True
		if 'Total' in datapartition.Type.unique() : isTotalEnergy=True
		if 'AirCondition' in datapartition.Type.unique(): isCooling=True
		if 'Share|Final Energy|Electricity|Cooling' in bigdata.variable : isShareCooling=True
		for region in cfg['partition'][partitionDemand]:
			
			# Heat has always to be in the data
			if isHeat: HeatEnergy=datapartition[ (datapartition.Zone==region) & (datapartition.Type == 'ElecHeating') ]['value'].mean()
			else: HeatEnergy=0
		
			# TransportEnergy is used only if the demand from EV is not coming from elsewhere; in this case it has to be in the data
			if isTransport: TransportEnergy=datapartition[ (datapartition.Zone==region) & (datapartition.Type == 'ElecVehicle') ]['value'].mean()
			else: TransportEnergy=0
			
			if isOtherAndCooling: 
				OtherAndCoolingEnergy=datapartition[ (datapartition.Zone==region) & (datapartition.Type == 'NonThermoAndCooling') ]['value'].mean()
				TotalEnergy=OtherAndCoolingEnergy+HeatEnergy+TransportEnergy
			
			if isNonthermo: nonthermoEnergy=datapartition[ (datapartition.Zone==region) & (datapartition.Type == 'nonthermo') ]['value'].mean()
			else: nonthermoEnergy=0
			
			if isTotalEnergy: TotalEnergy=datapartition[ (datapartition.Zone==region) & (datapartition.Type == 'Total') ]['value'].mean()
				
			if isCooling: CoolingEnergy=datapartition[ (datapartition.Zone==region) & (datapartition.Type == 'AirCondition') ]['value'].mean()
			elif isShareCooling:
				ShareCooling=bigdata.filter(region=region,variable='Share|Final Energy|Electricity|Cooling').as_pandas(meta_cols=False)['value'].mean()
				if isTotalEnergy : 
					CoolingEnergy=TotalEnergy*(ShareCooling/100)
					if not isNonthermo: nonthermoEnergy=TotalEnergy-HeatEnergy-TransportEnergy-CoolingEnergy
				elif isOtherAndCooling: 
					CoolingEnergy=(HeatEnergy+TransportEnergy+OtherAndCoolingEnergy)*(ShareCooling/100)
					if not isNonthermo: nonthermoEnergy=OtherAndCoolingEnergy-CoolingEnergy
				else : CoolingEnergy=0
			else : CoolingEnergy=0
			
			# Total Energy is computed if not present
			if not isTotalEnergy: TotalEnergy=HeatEnergy+CoolingEnergy+nonthermoEnergy+TransportEnergy
		
			Primary=datapartition[ (datapartition.Zone==region) & (datapartition.Type == 'PrimaryDemand') ]['value'].mean()
			Secondary=datapartition[ (datapartition.Zone==region) & (datapartition.Type == 'SecondaryDemand') ]['value'].mean()			

			if not isCooling:
				newdata=pd.DataFrame({'Type':['AirCondition'],'Unit':['MWh/yr'],\
					'Zone':[region],'model':['Recalculated'],'scenario':[cfg['listdatagroups'][0]],\
					'value':[CoolingEnergy],'year':[cfg['year']]})
				datapartition=pd.concat([datapartition,newdata],ignore_index=True)
			if not isNonthermo:
				newdata=pd.DataFrame({'Type':['nonthermo'],'Unit':['MWh/yr'],\
					'Zone':[region],'model':['Recalculated'],'scenario':[cfg['listdatagroups'][0]],\
					'value':[nonthermoEnergy],'year':[cfg['year']]})
				datapartition=pd.concat([datapartition,newdata],ignore_index=True)
			
			newdata=pd.DataFrame({'Type':['MaxActivePowerDemand','CostActivePowerDemand','MaxPrimaryDemand','CostPrimaryDemand',\
				'MaxSecondaryDemand','CostSecondaryDemand'],'Unit':['MW','EUR/MWh','MW','EUR/MWh','MW','EUR/MWh'],\
				'Zone':[region, region,region, region,region, region],'model':['Recalculated',\
				'Recalculated','Recalculated','Recalculated',\
				'Recalculated','Recalculated'],\
				'scenario':[cfg['scenario'],cfg['scenario'],cfg['scenario'],\
				cfg['scenario'],cfg['scenario'],cfg['scenario']],\
				'value':[MaxDemand,CostDemand,MaxPrimary,CostPrimary,MaxSecondary,CostSecondary],\
				'year':[cfg['year'],cfg['year'],cfg['year'],cfg['year'],cfg['year'],cfg['year']]})
			datapartition=pd.concat([datapartition,newdata],ignore_index=True)

		# include timeseries names from TimeSeries dictionnary and compute scaling coefficient
		print('include time series and compute scaling coefficients')
		for row in datapartition.index:
			mytype=datapartition.loc[row,'Type']
			if mytype in timeseriesdict['ZV'].keys():
				filetimeserie=timeseriesdict['ZV'][datapartition.loc[row,'Type']][datapartition.loc[row,'Zone']]
				datapartition.loc[row, 'Profile_Timeserie']=filetimeserie

		columnsZV=['Type','Zone','value','Profile_Timeserie']
		datapartition=datapartition[columnsZV]
		datapartition.to_csv(outputdir+cfg['treat']['ZV'], index=False)

	# treat global variables
	globalvars=pd.Series(str)
	for datagroup in cfg['listdatagroups']:
		print('treat datagroup ',datagroup)
		if 'techno' in cfg['datagroups'][datagroup]['listvariables'].keys():
			for techno in cfg['datagroups'][datagroup]['listvariables']['techno'].keys():
				if 'global' in cfg['datagroups'][datagroup]['listvariables']['techno'][techno].keys():
					print('there are global vars for:',datagroup,',techno:',techno)
					if type(cfg['datagroups'][datagroup]['listvariables']['techno'][techno]['global'])==list:
						for var in cfg['datagroups'][datagroup]['listvariables']['techno'][techno]['global']:
							for fuel in cfg['technos'][techno]:
								globalvars[var+fuel]=cfg['datagroups'][datagroup]['regions']['global'] 
					else:
						for key in cfg['datagroups'][datagroup]['listvariables']['techno'][techno]['global'].keys():
							for var in cfg['datagroups'][datagroup]['listvariables']['techno'][techno]['global'][key]['variables']:
								for fuel in cfg['datagroups'][datagroup]['listvariables']['techno'][techno]['global'][key]['fuels']:
									globalvars[var+fuel]=cfg['datagroups'][datagroup]['regions']['global'] 
		if 'coupling' in cfg['datagroups'][datagroup]['listvariables'].keys():
			if 'global' in cfg['datagroups'][datagroup]['listvariables']['coupling'].keys():
				for var in cfg['datagroups'][datagroup]['listvariables']['coupling']['global']:
					globalvars[var]=cfg['datagroups'][datagroup]['regions']['global']


	# create file TU_ThermalUnits
	###############################################################

	if cfg['treat']['TU']:
		print('Treating ThermalUnits')
		listvar=[]
		listvarout=['Zone','Name','NumberUnit','MaxPower','VariableCost']
		isCO2=False
		isDynamic=cfg['Parameters']['DynamicConstraints']
		isPrice=(cfg['Parameters']['thermal']['variablecost']=='Price')
		isMaintenance=False
		
		for variable in list(vardict['Input']['VarTU'].keys()):
			oevar=vardict['Input']['VarTU'][variable]
			if variable!='NumberUnits':
				listvar.append(oevar)
			
		v=0
		# loop on technos 
		for oetechno in cfg['technos']['thermal']:
			print('treat ',oetechno)
			TU=pd.DataFrame({'Name':oetechno,'region':listregions})
			TU=TU.set_index('region')
			for variable in vardict['Input']['VarTU']:
				isFuel=False
				TreatVar=True
				if variable=='Price' and 'thermal' in cfg['Parameters'] and cfg['Parameters']['thermal']['variablecost']=='Price':
					# case where VariableCost is computed as Efficency*Price of fuel
					if oetechno in cfg['Parameters']['thermal']['fuel']:
						fuel=cfg['Parameters']['thermal']['fuel'][oetechno]
						varname=vardict['Input']['VarTU'][variable]+fuel
						isFuel=True
					else: 
						TreatVar=False
				else:	
					varname=vardict['Input']['VarTU'][variable]+oetechno
				
				if TreatVar:
					vardf=bigdata.filter(variable=varname,region=listregions).as_pandas(meta_cols=False)
					vardf=vardf.set_index('region')
					vardf=vardf.rename(columns={"value":variable})
					dataTU=vardf[variable]
					
					# treat global variables
					isGlobal=False
					Global=0
					if vardict['Input']['VarTU'][variable]+oetechno in globalvars.index:
						print('variable ',variable,' ',varname,' is global for region ',globalvars[vardict['Input']['VarTU'][variable]+oetechno],' techno ',oetechno)
						isGlobal=True
						Global=dataTU[globalvars[vardict['Input']['VarTU'][variable]+oetechno] ]
					if isFuel:
						if vardict['Input']['VarTU'][variable]+fuel in globalvars.index:
							print('variable ',variable,' ',varname,' is global for region ',globalvars[vardict['Input']['VarTU'][variable]+fuel],' fuel ',fuel)
							isGlobal=True
							Global=dataTU[globalvars[vardict['Input']['VarTU'][variable]+fuel] ]
						
					TU=pd.concat([TU, dataTU], axis=1)
					if isGlobal: TU[variable]=Global
				else:
					TU[variable]=0.0
			TU=TU.fillna(value=0.0)
			# replace low capacities with 0
			TU.loc[ TU['Capacity'] < cfg['Parameters']['zerocapacity'], 'Capacity' ]=0
			
			# case with investment optimisation
			if isInvest and ('thermal' in cfg['Parameters']['CapacityExpansion']):
				if 'InvestmentCost' not in TU.columns:
					if oetechno in cfg['Parameters']['CapacityExpansion']['thermal']:
						if 'InvestmentCost' in cfg['Parameters']['CapacityExpansion']['thermal'][oetechno]:
							TU['InvestmentCost']=cfg['Parameters']['CapacityExpansion']['thermal'][oetechno]['InvestmentCost']
						else:
							TU['InvestmentCost']=0
					else:
						TU['InvestmentCost']=0
				if oetechno in cfg['Parameters']['CapacityExpansion']['thermal']:
					#replace 0 capacity with investment minimal capacity
					TU.loc[ TU['Capacity'] == 0, 'Capacity' ]=cfg['Parameters']['zerocapacity']
					TU['MaxAddedCapacity']=cfg['Parameters']['CapacityExpansion']['thermal'][oetechno]['MaxAdd']
					TU['MaxRetCapacity']=cfg['Parameters']['CapacityExpansion']['thermal'][oetechno]['MaxRet']
				else:
					TU['MaxAddedCapacity']=0
					TU['MaxRetCapacity']=0
			
			RowsToDelete = TU[ TU['Capacity'] == 0 ].index
			# Delete row with 0 capacity
			TU=TU.drop(RowsToDelete)
						
			if 'thermal' in cfg['Parameters']:
				if 'NbUnitsPerTechno' in cfg['Parameters']['thermal']:
					if cfg['Parameters']['thermal']['NbUnitsPerTechno']==1:
						TU['MaxPower']=TU['Capacity']
					else: isMaxPower=True
			
			if not cfg['Parameters']['DynamicConstraints']:
				TU['MinPower']=0.0			
					
			if len(TU.index)>0:				
				TU['NumberUnits']=1
				if 'thermal' in cfg['Parameters']:
					if 'NbUnitsPerTechno' in cfg['Parameters']['thermal']:
						if not cfg['Parameters']['thermal']['NbUnitsPerTechno']==1:
							TU['NumberUnits']=np.ceil(TU['Capacity']/TU['MaxPower'])
				
				if 'CO2Rate' in TU.columns: 
					TU['CO2']=TU['CO2Rate']
					isCO2=True
				elif ('CO2Emission' in TU.columns) & ('Energy' in TU.columns): 
					TU['CO2']=TU['CO2Emission']/TU['Energy']
					isCO2=True
				else: 
					TU['CO2']=0.0
					
				# Case where Variable Cost is computed out of Efficiency and Price
				if isPrice and oetechno in cfg['Parameters']['thermal']['fuel']: 
					if 'Efficiency' in TU.columns and 'Price' in TU.columns:
						TU['VariableCost']=TU['Efficiency']*TU['Price']
					elif 'Price' in TU.columns:
						TU['VariableCost']=TU['Price']

				# MaxPower=MaxPower*timestep in case of duration > 1h
				TU['MaxPower']=TU['MaxPower']*timestepduration
				TU['MinPower']=TU['MinPower']*timestepduration
				if v==0:	
					BigTU=TU
					v=1
				else:
					BigTU=pd.concat([BigTU,TU])
		BigTU['Zone']=BigTU.index
		listTU=BigTU.columns.tolist()
		listcols= ['Zone','Name','NumberUnits','MaxPower','VariableCost','FixedCost','InvestmentCost']
		if 'Capacity' in listTU: listcols.append('Capacity')
		if 'Energy' in listTU: listcols.append('Energy')
		if isDynamic:
			if 'MinPower' in listTU: listcols.append('MinPower')
			if 'DeltaRampUp' in listTU: listcols.append('DeltaRampUp')
			if 'DeltaRampDown' in listTU: listcols.append('DeltaRampDown')
			if 'MinUpTime' in listTU: listcols.append('MinUpTime')
			if 'MinDownTime' in listTU: listcols.append('MinDownTime')
			if 'StartUpCost' in listTU: listcols.append('StartUpCost')
		
		if isCO2 and 'CO2' in listTU: listcols.append(['CO2'])
		if isPrice: 
			if 'Price' in listTU: listcols.append(['Price'])
			if 'Efficiency' in listTU : listcols.append(['Efficiency'])
		if isInertia and 'Inertia' in listTU: listcols.append(['Inertia'])
		if isPrimary and 'PrimaryRho' in listTU: listcols.append(['PrimaryRho'])
		if isSecondary and 'SecondaryRho' in listTU: listcols.append(['SecondaryRho'])
		if isMaintenance and 'MaxPowerProfile' in listTU: listcols.append(['MaxPowerProfile'])
		if 'InitialPower' in listTU: listcols.append(['InitialPower'])
		if 'InitUpDownTime' in listTU: listcols.append(['InitUpDownTime'])
		if 'Pauxiliary' in listTU: listcols.append(['Pauxiliary'])
		if 'QuadTerm' in listTU: listcols.append(['QuadTerm'])
		if isInvest and 'thermal' in cfg['Parameters']['CapacityExpansion']:
			if 'InvestmentCost' in BigTU.columns: listcols.append('InvestmentCost')
			if 'MaxAddedCapacity' in BigTU.columns: listcols.append('MaxAddedCapacity')
			if 'MaxRetCapacity' in BigTU.columns: listcols.append('MaxRetCapacity')
		
		BigTU=BigTU[ listcols ]
		
		BigTU=BigTU[ BigTU['Zone'].isin(cfg['partition'][partitionDemand]) ]
		BigTU=BigTU[BigTU.NumberUnits >0]
		BigTU.to_csv(outputdir+cfg['treat']['TU'], index=False)

	# treat seasonal storage
	# filling sheet SS_SeasonalStorage and STS_ShortTermStorage
	############################################################
	AddedCapa=pd.DataFrame()
	if cfg['treat']['SS']:
		print('Treating SeasonalStorage')
		v=0
		for oetechno in	cfg['technos']['reservoir']:
			print('treat ',oetechno)
			SS=pd.DataFrame({'Name':oetechno,'region':listregions})
			SS=SS.set_index('region')
			
			for variable in vardict['Input']['VarSS']:
				varname=vardict['Input']['VarSS'][variable]+'Hydro|'+oetechno
				vardf=bigdata.filter(variable=varname,region=listregions).as_pandas(meta_cols=False)
				vardf=vardf.set_index('region')
				data=vardf[['value']]
				data=data.rename(columns={"value":variable})
				
				# treat global variables
				isGlobal=False
				Global=0
				if varname in globalvars.index:
					print('variable ',variable,' ',varname,' is global for region ',globalvars[varname],' techno ',oetechno)
					isGlobal=True
					Global=data[variable][globalvars[varname] ]
					
				SS=pd.concat([SS, data], axis=1)
				if isGlobal: SS[variable]=Global
					
			SS=SS.fillna(value=0.0)
			
			# replace low capacities with 0
			SS.loc[ SS['MaxPower'] < cfg['Parameters']['zerocapacity'], 'MaxPower' ]=0
			RowsToDelete = SS[ SS['MaxPower'] == 0 ].index
			# Delete these row indexes from dataFrame
			SS=SS.drop(RowsToDelete)
			
			# include inflows profiles: include timeseries names from TimeSeries dictionnary
			SS['InflowsProfile']=''
			SS['WaterValues']=''
			SS['Energy_Timeserie']=0
			SS['HydroSystem']=0
			SS['Name']=oetechno
			SS['Zone']=SS.index
			SS['AddPumpedStorage']=0
			SS['AddPumpedStorageVolume']=0
			SS['InitialVolume']=0
			for row in SS.index:
				# treatment initial volume
				if row in cfg['aggregateregions']:
					if (row in cfg['aggregateregions'] and SS.loc[row,'MaxVolume']>0 and SS.loc[row,'MaxPower']>cfg['Parameters']['reservoir']['minpowerMWh']):
						Rate=0
						N=0
						for reg in cfg['aggregateregions'][row]:
							if reg in cfg['Parameters']['InitialFillingrate']:
								Rate=Rate+cfg['Parameters']['InitialFillingrate'][reg]
								N=N+1
						if N>0:
							Rate=Rate/N
						SS.loc[row,'InitialVolume']=SS.loc[row,'MaxVolume']*Rate
				elif (SS.loc[row,'MaxVolume']>0 and SS.loc[row,'MaxPower']>cfg['Parameters']['reservoir']['minpowerMWh']):
					SS.loc[row,'InitialVolume']=SS.loc[row,'MaxVolume']*cfg['Parameters']['InitialFillingrate'][row]
					
				# treatment volume when no max storage is provided or MaxPower<minpowerMWh or no inflows
				if SS.loc[row,'MaxVolume']==0 or SS.loc[row,'MaxPower']<cfg['Parameters']['reservoir']['minpowerMWh'] or SS.loc[row,'Inflows']==0:
					# this storage is moved to Additionnal Pumped Storage
					SS.loc[row,'AddPumpedStorage']=SS.loc[row,'MaxPower']
					SS.loc[row,'AddPumpedStorageVolume']=SS.loc[row,'MaxVolume']
					print('No volume for reservoir in region '+row+', adding capacity to Pumped Storage')
				# treatment inflows timeseries
				if row in timeseriesdict['SS']['Inflows'].keys():
					filetimeserie=timeseriesdict['SS']['Inflows'][row]
					SS.loc[row, 'InflowsProfile']=filetimeserie

			SS['NumberUnits']=SS.apply(lambda x: 1 if x['MaxVolume'] > 0 else 0, axis = 1)
			SS['Zone']=SS.index
			SS['MinVolume']=0
			SS['MinPower']=0
			SS['TurbineEfficiency']=1.0
			SS['PumpingEfficiency']=0.0
			SS['MaxPower']=SS['MaxPower']*timestepduration
			SS['Inflows']=SS['Inflows']*timestepduration			
			# create df for addedcapacity
			AddedCapa=SS[SS.AddPumpedStorage >0]
			
			# remove rows where MaxVolume=0 or where MaxPower < minPowerMWh
			SS = SS.drop(SS[SS.MaxVolume == 0].index)
			SS = SS.drop(SS[SS.MaxPower < cfg['Parameters']['reservoir']['minpowerMWh']].index)
			
			if v==0:
				BigSS=SS
				v=1
			else:
				BigSS=pd.concat([BigSS,SS])
		
		listSS=BigSS.columns.tolist()
		listcols= ['Name','Zone','HydroSystem','NumberUnits','MaxPower','MinPower',
		'MaxVolume','MinVolume','Inflows','InflowsProfile','InitialVolume', 
		'TurbineEfficiency','PumpingEfficiency','AddPumpedStorage']

		if isInertia and 'Inertia' in listSS: listcols.append('Inertia')
		if isPrimary and 'PrimaryRho' in listSS: listcols.append('PrimaryRho')
		if isSecondary and 'SecondaryRho' in listSS: listcols.append('SecondaryRho')

		BigSS=BigSS[ listcols ]
		
		BigSS=BigSS[ BigSS['Zone'].isin(cfg['partition'][partitionDemand]) ]
		BigSS.to_csv(outputdir+cfg['treat']['SS'], index=False)

	# filling sheet STS_ShortTermStorage
	###############################################################	

	if cfg['treat']['STS']:	
		print('Treating Short Term Storage')
		v=0
		STS=pd.DataFrame({'region':listregions})
		STS=STS.set_index('region')
		
		# treat short term hydro storage
		isVarHydroStorage=pd.Series()
		for oetechno in	cfg['technos']['hydrostorage']:
			print('treat ',oetechno)
			for variable in vardict['Input']['VarSTS|Hydro']:
				varname=vardict['Input']['VarSTS|Hydro'][variable]+'Hydro|'+oetechno
				vardf=bigdata.filter(variable=varname,region=listregions).as_pandas(meta_cols=False)
				if len(vardf.index)>0: 
					isVarHydroStorage[variable]=True
				else:
					isVarHydroStorage[variable]=False
				vardf=vardf.set_index('region')
				data=vardf[['value']]
				data=data.rename(columns={"value":variable})
				
				isGlobal=False
				Global=0
				# treat global variables
				if varname in globalvars.index:
					print('variable ',variable,' ',varname,' is global for region ',globalvars[varname],' techno ',oetechno)
					isGlobal=True
					Global=data[variable][globalvars[varname] ]

				STS=pd.concat([STS, data], axis=1)	

				if isGlobal: STS[variable]=Global
				
			STS=STS.fillna(value=0.0)
			
			# replace low capacities with 0
			STS.loc[ STS['MaxPower'] < cfg['Parameters']['zerocapacity'], 'MaxPower' ]=0
	
			# case with investment: replace 0 capacity with investment minimal capacity
			if cfg['Parameters']['invest'] and oetechno in cfg['technosinvest']['hydrostorage']:
				STS.loc[ STS['MaxPower'] == 0, 'MaxPower' ]=cfg['Parameters']['zerocapacity']
			
			# compute max storage or max power if not in data
			isMaxPower=False
			isMaxVolume=False
			if 'MaxPower' in STS.columns and not (STS==0).all()['MaxPower']: 
				isMaxPower=True
			if 'MaxVolume' in STS.columns and not (STS==0).all()['MaxVolume']: 
				isMaxVolume=True
			
			# case where Maximum Power is not in the data
			if isMaxVolume and not isMaxPower: 
				STS['MaxPower']=STS['MaxVolume']/cfg['Parameters']['Volume2CapacityRatio']['hydrostorage'][oetechno]
				
			# case where Maximum Storage is not in the data
			if isMaxPower and not isMaxVolume: 
				STS['MaxVolume']=STS['MaxPower']*cfg['Parameters']['Volume2CapacityRatio']['hydrostorage'][oetechno]
			
			# treat additionnal pumped storage from SS
			STS['AddPumpedStorage']=0
			STS['AddPumpedStorageVolume']=0
			STS['MaxPower']=STS['MaxPower']*timestepduration
			STS['MinPower']=-1*STS['MaxPower']
			for row in STS.index:
				if row in AddedCapa.index:
					print('Adding additionnal capacity: '+str(AddedCapa.loc[row,'AddPumpedStorage'])+' for Pumped Storage in region '+row)
					STS.loc[row,'MaxPower']=STS.loc[row,'MaxPower']+AddedCapa.loc[row,'AddPumpedStorage']*timestepduration
					STS.loc[row,'MaxVolume']=STS.loc[row,'MaxVolume']+AddedCapa.loc[row,'AddPumpedStorageVolume']
					STS.loc[row,'AddPumpedStorage']=AddedCapa.loc[row,'AddPumpedStorage']
					STS.loc[row,'AddPumpedStorageVolume']=AddedCapa.loc[row,'AddPumpedStorageVolume']
			RowsToDelete = STS[ STS['MaxPower'] == 0 ].index
			# Delete row with 0 capacity
			STS=STS.drop(RowsToDelete)
			STS['Name']=oetechno
			STS['Zone']=STS.index
			STS['NumberUnits']=1	
			STS['Inflows']=0	
			STS['TurbineEfficiency']=1.0
			STS['MinVolume']=0	
			STS['InitialVolume']=0	
			STS['Zone']=STS.index
			if 'PrimaryRho' in STS.columns: STS['MaxPrimaryPower']=STS['MaxPower']*STS['PrimaryRho']
			if 'SecondaryRho' in STS.columns: STS['MaxSecondaryPower']=STS['MaxPower']*STS['SecondaryRho']
			STS['MinPowerCoef']=1.0
			STS['MaxPowerCoef']=1.0
			if 'PumpingEfficiency' not in STS.columns:
				STS['PumpingEfficiency']=cfg['Parameters']['PumpingEfficiency']['hydrostorage']['Pumped Storage']

			if v==0:
				BigSTS=STS
				v=1
			else:
				BigSTS=pd.concat([BigSTS,STS])

		print(' ')
		print('BATTERIES')

		# treat batteries
		isVarBattery=pd.Series()
		for oetechno in	cfg['technos']['battery']:
			print('traitement ',oetechno)
			BAT=pd.DataFrame({'region':listregions})
			BAT=BAT.set_index('region')
			for variable in vardict['Input']['VarSTS|Battery']:
				varname=vardict['Input']['VarSTS|Battery'][variable]+oetechno
				vardf=bigdata.filter(variable=varname,region=listregions).as_pandas(meta_cols=False)
				if len(vardf.index)>0: 
					isVarBattery[variable]=True
				else:
					isVarBattery[variable]=False
				vardf=vardf.set_index('region')
				data=vardf[['value']]
				data=data.rename(columns={"value":variable})
				
				# treat global variables
				isGlobal=False
				Global=0
				if varname in globalvars.index:
					print('variable ',variable,' ',varname,' is global for region ',globalvars[varname],' techno ',oetechno)
					isGlobal=True
					Global=data[variable][globalvars[varname] ]
					
				BAT=pd.concat([BAT, data], axis=1)	
				if isGlobal: BAT[variable]=Global
				
			BAT=BAT.fillna(value=0.0)
			isMaxPower=False
			isMaxVolume=False
			if 'MaxPower' in BAT.columns and not (BAT==0).all()['MaxPower']: 
				isMaxPower=True
			if 'MaxVolume' in BAT.columns and not (BAT==0).all()['MaxVolume']: 
				isMaxVolume=True
			if 'MaxPower' not in BAT.columns and 'MaxVolume' not in BAT.columns: print('no data')
			
			# replace low capacities with 0
			if isMaxPower: BAT.loc[ BAT['MaxPower'] < cfg['Parameters']['zerocapacity'], 'MaxPower' ]=0
			if isMaxVolume: BAT.loc[ BAT['MaxVolume'] < cfg['Parameters']['zerocapacity']*cfg['Parameters']['Volume2CapacityRatio']['battery'][oetechno], 'MaxVolume' ]=0
	
			# case with investment
			if isInvest and 'battery' in cfg['Parameters']['CapacityExpansion']:
				if not isVarBattery['InvestmentCost']:
					if oetechno in cfg['Parameters']['CapacityExpansion']['battery']:
						if 'InvestmentCost' in cfg['Parameters']['CapacityExpansion']['battery'][oetechno]:
							BAT['InvestmentCost']=cfg['Parameters']['CapacityExpansion']['battery'][oetechno]['InvestmentCost']
						else:
							BAT['InvestmentCost']=0
					else:
						BAT['InvestmentCost']=0
				if oetechno in cfg['Parameters']['CapacityExpansion']['battery']:
					# replace 0 capacity with investment minimal capacity
					if isMaxPower: BAT.loc[ BAT['MaxPower'] == 0, 'MaxPower' ]=cfg['Parameters']['zerocapacity']
					if isMaxVolume: BAT.loc[ BAT['MaxVolume'] == 0, 'MaxVolume' ]=cfg['Parameters']['zerocapacity']*cfg['Parameters']['Volume2CapacityRatio']['battery'][oetechno]
					BAT['MaxAddedCapacity']=cfg['Parameters']['CapacityExpansion']['battery'][oetechno]['MaxAdd']
					BAT['MaxRetCapacity']=cfg['Parameters']['CapacityExpansion']['battery'][oetechno]['MaxRet']
				else:
					BAT['MaxAddedCapacity']=0
					BAT['MaxRetCapacity']=0
			print(BAT)
			RowsToDelete=[]
			if isMaxPower: RowsToDelete = BAT[ BAT['MaxPower'] == 0 ].index
			if isMaxVolume: RowsToDelete = BAT[ BAT['MaxVolume'] == 0 ].index
			print(RowsToDelete)
			# Delete row with 0 capacity
			print(RowsToDelete)
			BAT=BAT.drop(RowsToDelete)
			print(BAT)
			
			BAT['Name']=oetechno
			BAT['Zone']=BAT.index
			BAT['NumberUnits']=1	
			BAT['Inflows']=0	
			BAT['TurbineEfficiency']=1.0
			
			# case where Maximum Discharge/Charge is not in the data
			if not isMaxPower: 
				BAT['MaxPower']=BAT['MaxVolume']/cfg['Parameters']['Volume2CapacityRatio']['battery'][oetechno]
				
			# case where Maximum Charge is not in the data
			if 'MinPower' not in BAT.columns or ('MinPower'  in BAT.columns and (BAT==0).all()['MinPower']): 
				BAT['MinPower']=-1*BAT['MaxPower']
			else:
				BAT['MinPower']=-1*BAT['MinPower']
				
			# case where Maximum Storage is not in the data
			if not isMaxVolume:
				BAT['MaxVolume']=BAT['MaxPower']*cfg['Parameters']['Volume2CapacityRatio']['battery'][oetechno]
				
			BAT['MaxPower']=BAT['MaxPower']*timestepduration
			BAT['MinPower']=BAT['MinPower']*timestepduration			
			BAT['MinVolume']=0
			BAT['InitialVolume']=0			
			BAT['Zone']=BAT.index
			if 'PrimaryRho' in STS.columns: BAT['MaxPrimaryPower']=BAT['MaxPower']*BAT['PrimaryRho']
			if 'SecondaryRho' in STS.columns: BAT['MaxSecondaryPower']=BAT['MaxPower']*BAT['SecondaryRho']
			BAT['AddPumpedStorage']=0
			BAT['MinPowerCoef']=1.0
			BAT['MaxPowerCoef']=1.0
			
			if 'PumpingEfficiency' not in BAT.columns:
				BAT['PumpingEfficiency']=cfg['Parameters']['PumpingEfficiency']['battery'][oetechno]
			print(BAT)
			if v==0:
				BigSTS=BAT
				v=1
			else:
				BigSTS=pd.concat([BigSTS,BAT])
				
		# create blank time series dataframe
		start2050=pd.to_datetime('2050-01-01T00:00+01:00')
		end2050=pd.to_datetime('2050-12-31T23:00+01:00')
		TimeIndex=pd.date_range(start=start2050,end=end2050, freq='1H')	
		
		# treat demand response 'load shifting'
		if 'demandresponseloadshifting' in cfg['technos'].keys():
			print('treat demand response load shifting')
			DRTimeSeries=pd.DataFrame()
			
			ParticipationRate=pd.read_csv(cfg['Parameters']['DemandResponseLoadShifting']['participationRateData'])
			ParticipationRate=ParticipationRate.groupby('countryname').mean()
				
			MaxDispatchName=vardict['Input']['VarSTS|DemandResponseLoadShifting']['MaxDispatch']
			MaxReductionName=vardict['Input']['VarSTS|DemandResponseLoadShifting']['MaxReduction']
			
			# loop on appliances
			for appliance in cfg['technos']['demandresponseloadshifting']:
				print('treat ',appliance)
				DRLS=pd.DataFrame({'region':cfg['partition'][partitionDemand]})
				DRLS=DRLS.set_index('region')
				EMminusE=pd.Series(index={'region':cfg['partition'][partitionDemand]})
				
				tshift=int(cfg['Parameters']['DemandResponseLoadShifting']['tshift'][appliance])
				NumberBalancing=int(len(TimeIndex)/tshift)
				
				# loop on regions
				for reg in cfg['partition'][partitionDemand]:
					if cfg['Parameters']['DemandResponseLoadShifting']['participationRate']:
						if reg in cfg['aggregateregions']:
							N=0.0
							PartRate=0.0
							for country in cfg['aggregateregions'][reg]:
								if country in ParticipationRate.index:
									N=N+1.0
									PartRate=PartRate+ParticipationRate.at[country,appliance]
							PartRate=PartRate/N
						else: 
							PartRate=ParticipationRate.at[reg,appliance]
					else:
						PartRate=1.0
					MaxDispatchData=bigdata_SubAnnual.filter(variable=MaxDispatchName+appliance,region=reg).as_pandas(meta_cols=False).reset_index()
					MaxReductionData=bigdata_SubAnnual.filter(variable=MaxReductionName+appliance,region=reg).as_pandas(meta_cols=False).reset_index()
					
					# compute EM-E
					EMminusE[reg]=0
					Balancing=0
					NumberBalancingInData=int(12*24/tshift)
					for IndexBalancing in range(NumberBalancingInData):
						MaxDispatchData_IndexBalancing=MaxDispatchData[ (MaxDispatchData.index>=IndexBalancing*tshift) & (MaxDispatchData.index<=(IndexBalancing+1)*tshift-1) ]
						MaxReductionData_IndexBalancing=MaxReductionData[ (MaxReductionData.index>=IndexBalancing*tshift) & (MaxReductionData.index<=(IndexBalancing+1)*tshift-1) ]
						EMminusE_IndexBalancing=MaxDispatchData_IndexBalancing['value'].sum()  #-MaxReductionData_IndexBalancing['value'].sum()
						if EMminusE_IndexBalancing>	EMminusE[reg]: EMminusE[reg]=EMminusE_IndexBalancing
					EMminusE[reg]=EMminusE[reg]*PartRate
						
					# create MaxDispatch and MaxReduction time series
					# the data give a representative day for each month which has to be extended to all days
					MaxDispatchData['subannual']=pd.to_datetime(MaxDispatchData['subannual'],format='%m-%d %H:%S+01:00')+pd.DateOffset(years=150)
					MaxReductionData['subannual']=pd.to_datetime(MaxReductionData['subannual'],format='%m-%d %H:%S+01:00')+pd.DateOffset(years=150)
					MaxDispatch=pd.Series()
					MaxReduction=pd.Series()
					for month in range(12):
						numberdays=monthrange(int(cfg['year']),month+1)[1]

						# get data for the current month
						MaxDispatchDataFirstDay=MaxDispatchData[ MaxDispatchData.subannual.dt.month==month+1 ]
						MaxReductionDataFirstDay=MaxReductionData[ MaxReductionData.subannual.dt.month==month+1 ]
						
						# duplicate for all days of the month
						for day in range(numberdays):
							MaxDispatch=pd.concat([MaxDispatch,MaxDispatchDataFirstDay['value']])
							MaxReduction=pd.concat([MaxReduction,MaxReductionDataFirstDay['value']])
					
					MaxDispatch=np.maximum(MaxDispatch, 0)
					MaxDispatch=MaxDispatch*(1/cfg['Parameters']['DemandResponseCoefficient'])
					NameSerie='DR__'+appliance+'__'+reg
					DRTimeSeries[NameSerie+'__MaxPower']=MaxReduction*PartRate
					DRTimeSeries[NameSerie+'__MinPower']=-MaxDispatch*PartRate  #-cfg['Parameters']['DemandResponseCoefficient']
					DRTimeSeries[NameSerie+'__MaxDispatch']=MaxDispatch*PartRate
					DRTimeSeries[NameSerie+'__MinVolume']=0
					
					# include constraint MinVolume=EMminusE for all indexes =i*tshift
					DRTimeSeries[NameSerie+'__MinVolume'].mask( ((DRTimeSeries.index+1) % tshift) == 0, EMminusE[reg], inplace=True)

				DRLS['Name']=appliance
				DRLS['Zone']=DRLS.index
				DRLS['NumberUnits']=1	
				DRLS['Inflows']=0	
				DRLS['TurbineEfficiency']=1.0
				DRLS['PumpingEfficiency']=1.0
				DRLS['MinPower']='DR__'+appliance+'__'+DRLS.index+'__MinPower'	
				DRLS['MaxPower']='DR__'+appliance+'__'+DRLS.index+'__MaxPower'	
				DRLS['MinPowerCoef']=1.0
				DRLS['MaxPowerCoef']=1.0
				DRLS['MinVolume']='DR__'+appliance+'__'+DRLS.index+'__MinVolume'
				DRLS['MaxVolume']=EMminusE*cfg['Parameters']['DemandResponseCoefficient']
				DRLS['VolumeLevelTarget']=EMminusE		
				DRLS['InitialVolume']=EMminusE		
				DRLS['Zone']=DRLS.index
				DRLS['MaxPrimaryPower']=0
				DRLS['MaxSecondaryPower']=0
				DRLS['Inertia']=0
				DRLS['AddPumpedStorage']=0
				if v==0:
					BigSTS=DRLS
					v=1
				else:
					BigSTS=pd.concat([BigSTS,DRLS])
					
			#####################################"
		
		listcols= ['Name','Zone','NumberUnits','MaxPower','MaxVolume','TurbineEfficiency','PumpingEfficiency','MinPower','MinVolume','Energy','Inflows','InitialVolume','AddPumpedStorage']
		listSTS=BigSTS.columns.tolist()
		
		if isInertia and 'Inertia' in listSTS: listcols.append('Inertia')
		if isPrimary and 'MaxPrimaryPower' in listSTS: listcols.append('MaxPrimaryPower')
		if isSecondary and 'MaxSecondaryPower' in listSTS: listcols.append('MaxSecondaryPower')
		if 'VolumeLevelTarget' in listSTS: listcols.append('VolumeLevelTarget')
		if isInvest and 'battery' in cfg['Parameters']['CapacityExpansion']:
			if 'MaxAddedCapacity' in BigSTS.columns: listcols.append('MaxAddedCapacity')
			if 'MaxRetCapacity' in BigSTS.columns: listcols.append('MaxRetCapacity')
			if 'InvestmentCost' in BigSTS.columns: listcols.append('InvestmentCost')

		BigSTS=BigSTS[ listcols ]
		
		BigSTS=BigSTS[ BigSTS['Zone'].isin(cfg['partition'][partitionDemand]) ]
		BigSTS=BigSTS.fillna(0)
		BigSTS.to_csv(outputdir+cfg['treat']['STS'], index=False)
		
	# treating res
	if cfg['treat']['RES']:
		v=0
		print('Treating Renewable units')
		isVarRes=pd.Series()
		for oetechno in	cfg['technos']['res']+cfg['technos']['runofriver']:
			print('treat ',oetechno)
			RES=pd.DataFrame({'Name':oetechno,'region':listregions})
			RES=RES.set_index('region')
			for variable in vardict['Input']['VarRES']:
				varname=vardict['Input']['VarRES'][variable]+oetechno
				vardf=bigdata.filter(variable=varname,region=listregions).as_pandas(meta_cols=False)
				if len(vardf.index)>0: 
					isVarRes[variable]=True
				else:
					isVarRes[variable]=False
				vardf=vardf.set_index('region')
				data=vardf[['value']]
				data=data.rename(columns={"value":variable})			
				
				# treat global variables
				isGlobal=False
				Global=0
				if varname in globalvars.index:
					print(varname, ' is global')
					isGlobal=True
					Global=data[variable][globalvars[varname]]
					#RES[variable]=RES[variable][globalvars[vardict['Input']['VarRES'][variable]] ]
				
				RES=pd.concat([RES, data], axis=1)	
				if isGlobal: RES[variable]=Global
				
			RES=RES.fillna(value=0.0)
			
			# replace low capacities with 0
			RES.loc[ RES['MaxPower'] < cfg['Parameters']['zerocapacity'], 'MaxPower' ]=0
			
			# case with investment
			if isInvest and 'res' in cfg['Parameters']['CapacityExpansion']:
				if not isVarRes['InvestmentCost']:
					if oetechno in cfg['Parameters']['CapacityExpansion']['res']:
						if 'InvestmentCost' in cfg['Parameters']['CapacityExpansion']['res'][oetechno]:
							RES['InvestmentCost']=cfg['Parameters']['CapacityExpansion']['res'][oetechno]['InvestmentCost']
						else:
							RES['InvestmentCost']=0
					else:
						RES['InvestmentCost']=0
				if oetechno in cfg['Parameters']['CapacityExpansion']['res']:
					# replace 0 capacity with investment minimal capacity
					RES.loc[ RES['MaxPower'] == 0, 'MaxPower' ]=cfg['Parameters']['zerocapacity']
					RES['MaxAddedCapacity']=cfg['Parameters']['CapacityExpansion']['res'][oetechno]['MaxAdd']
					RES['MaxRetCapacity']=cfg['Parameters']['CapacityExpansion']['res'][oetechno]['MaxRet']
				else:
					RES['MaxAddedCapacity']=0
					RES['MaxRetCapacity']=0
			
			RowsToDelete = RES[ RES['MaxPower'] == 0 ].index
			# Delete row with 0 capacity
			RES=RES.drop(RowsToDelete)
			
			RES['Name']=oetechno
			RES['Zone']=RES.index
			RES['NumberUnits']=1	
			RES['MinPower']=0	
			RES['Kappa']=1	
			if 'PrimaryRho' in RES.columns and 'SecondaryRho' in RES.columns:
				RES['Gamma']=RES['PrimaryRho']+RES['SecondaryRho']
			
			# case of RoR: use energy instead of Capacity
			RES['Capacity']=RES['MaxPower']
			if oetechno in cfg['Parameters']['MultFactor'].keys():
				RES['MaxPower']=RES['Energy']
				# The sum on 1 year of MaxPower*Profile should be equal to energy
				# Capacity*8760*r=energy				
				# MaxPower must be multiplied by Energy/(Capacity*8760)
			
			# include renewable potential profiles: include timeseries names from TimeSeries Disctionnary
			RES['MaxPowerProfile']=''
			RES['Energy_Timeserie']=0
			for row in RES.index:
				if row in timeseriesdict['RES'][oetechno].keys():
					filetimeserie=timeseriesdict['RES'][oetechno][row]
					RES.loc[row, 'MaxPowerProfile']=filetimeserie
					# compute energy scaling coefficient in inflows
					# timeserie=pd.read_csv(cfg['dirTimeSeries']+filetimeserie,header=1,index_col=0)
					# energy=timeserie[cfg['UCScenarios']].sum(axis=0)
					# Energy=energy.mean()
					# RES.loc[row, 'Energy_Timeserie']=Energy
					
			if oetechno in cfg['technos']['runofriver']:
				RES['MaxPower']=RES['MaxPower']*timestepduration
			if v==0:
				BigRES=RES
				v=1
			else:
				BigRES=pd.concat([BigRES,RES])
		
		listRES=BigRES.columns.tolist()
		listcols= ['Name','Zone','NumberUnits','MaxPower','MinPower','MaxPowerProfile','Energy','Kappa','Capacity']
		if (isPrimary or isSecondary) and 'Gamma' in listRES: listcols.append('Gamma')
		if isInertia and 'Inertia' in listRES: listcols.append('Inertia')
		if isInvest and 'res' in cfg['Parameters']['CapacityExpansion']:
			if 'MaxAddedCapacity' in BigRES.columns: listcols.append('MaxAddedCapacity')
			if 'MaxRetCapacity' in BigRES.columns: listcols.append('MaxRetCapacity')
			if 'InvestmentCost' in BigRES.columns: listcols.append('InvestmentCost')

		BigRES=BigRES[ listcols ]
		BigRES=BigRES[ BigRES['Zone'].isin(cfg['partition'][partitionDemand]) ]
		BigRES=BigRES.fillna(0)
		BigRES.to_csv(outputdir+cfg['treat']['RES'], index=False)

