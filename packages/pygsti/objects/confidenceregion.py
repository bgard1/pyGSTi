#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation              
#    This Software is released under the GPL license detailed    
#    in the file "license.txt" in the top-level pyGSTi directory 
#*****************************************************************
""" Classes for constructing confidence regions """

import numpy as _np
import scipy.stats as _stats
import warnings as _warnings
from .. import optimize as _opt

from gateset import P_RANK_TOL

class ConfidenceRegion(object):
    """
    Encapsulates a hessian-based confidence region in gate-set space.

    A ConfidenceRegion computes and stores the quadratic form for an approximate 
    confidence region based on a confidence level and a hessian, typically of either
    loglikelihood function or its proxy, the chi2 function.
    """

    def __init__(self, gateset, hessian, confidenceLevel, 
                 gates=True, G0=True, SPAM=True, SP0=True,
                 hessianProjection="std"):
        """ 
        Initializes a new ConfidenceRegion.

        Parameters
        ----------
        gateset : GateSet
            the gate set point estimate that maximizes the logl or minimizes 
            the chi2, and marks the point in gateset-space where the Hessian
            has been evaluated.

        hessian : numpy array
            A nParams x nParams Hessian matrix, where nParams is the number 
            of dimensions of gateset space, i.e. 
            nParams = gateset.num_params(gates,G0,SPAM,SP0)

        confidenceLevel : float
            The confidence level as a percentage, i.e. between 0 and 100.

        gates,G0,SPAM,SP0 : bool, optional
            Specify how the gateset is parameterized.

        hessianProjection : string, optional
            Specifies how (and whether) to project the given hessian matrix
            onto a non-gauge space.  Allowed values are:

            - 'std' -- standard projection onto the space perpendicular to the
              gauge space.
            - 'none' -- no projection is performed.  Useful if the supplied
              hessian has already been projected.
            - 'optimal gate CIs' -- a lengthier projection process in which a
              numerical optimization is performed to find the non-gauge space
              which minimizes the (average) size of the confidence intervals
              corresponding to gate (as opposed to SPAM vector) parameters.
        """

        proj_non_gauge = gateset.get_nongauge_projector(gates,G0,SPAM,SP0)
        self.nNonGaugeParams = _np.linalg.matrix_rank(proj_non_gauge, P_RANK_TOL)
        self.nGaugeParams = hessian.shape[0] - self.nNonGaugeParams

        #Project Hessian onto non-gauge space
        if hessianProjection == 'none':
            projected_hessian = hessian
        elif hessianProjection == 'std':
            projected_hessian = _np.dot(proj_non_gauge, _np.dot(hessian, proj_non_gauge))
        elif hessianProjection == 'optimal gate CIs':
            projected_hessian = _optProjectionForGateCIs(gateset, hessian, self.nNonGaugeParams,
                                                         self.nGaugeParams, gates, G0, SPAM, SP0,
                                                         confidenceLevel, verbosity=3) #verbosity for DEBUG
        else:
            raise ValueError("Invalid value of hessianProjection argument: %s" % hessianProjection)


        #Scale projected Hessian for desired confidence level => quadratic form for confidence region
        # assume hessian gives Fisher info, so asymptotically normal => confidence interval = +/- seScaleFctr * 1/sqrt(hessian)
        # where seScaleFctr gives the scaling factor for a normal distribution, i.e. integrating the
        # std normal distribution between -seScaleFctr and seScaleFctr == confidenceLevel/100 (as a percentage)
        assert(confidenceLevel > 0.0 and confidenceLevel < 100.0)
        if confidenceLevel < 1.0: 
            _warnings.warn("You've specified a %f%% confidence interval, " % confidenceLevel \
                               + "which is usually small.  Be sure to specify this" \
                               + "number as a percentage in (0,100) and not a fraction in (0,1)." )

        # Get constants C such that xT*Hessian*x = C gives contour for the desired confidence region.
        #  C1 == Single DOF case: constant for a single-DOF likelihood, (or a profile likelihood in our case)
        #  Ck == Total DOF case: constant for a region of the likelihood as a function of *all non-gauge* gateset parameters
        C1 = _stats.chi2.ppf(confidenceLevel/100.0, 1)
        Ck = _stats.chi2.ppf(confidenceLevel/100.0, self.nNonGaugeParams)

          # Alt. method to get C1: square the result of a single gaussian (normal distribution)
          #Note: scipy's ppf gives inverse of cdf, so want to know where cdf == the leftover probability on left side
        seScaleFctr = -_stats.norm.ppf((1.0 - confidenceLevel/100.0)/2.0) #std error scaling factor for desired confidence region
        assert(_np.isclose(C1, seScaleFctr**2))

        # save quadratic form Q s.t. xT*Q*x = 1 gives confidence region using C1, i.e. a
        #  region appropriate for generating 1-D confidence intervals.
        self.regionQuadcForm = projected_hessian / C1
        self.intervalScaling = _np.sqrt( Ck / C1 ) # multiplicative scaling required to convert intervals
                                                   # to those obtained using a full (using Ck) confidence region.
        #print "DEBUG: C1 =",C1," Ck =",Ck," scaling =",self.intervalScaling

        #Invert *non-gauge-part* of quadratic by eigen-decomposing -> 
        #   inverting the non-gauge eigenvalues -> re-constructing via eigenvectors.
        # (Note that Hessian & quadc form mxs are symmetric so eigenvalues == singular values)        
        evals,U = _np.linalg.eigh(self.regionQuadcForm)  # regionQuadcForm = U * diag(evals) * U.dag (b/c U.dag == inv(U) )
        Udag = _np.conjugate(_np.transpose(U))

          #invert only the non-gauge eigenvalues (those with ordering index >= nGaugeParams)
        orderInds = [ el[0] for el in sorted( enumerate(evals), key=lambda x: abs(x[1])) ] # ordering index of each eigenvalue
        invEvals = _np.zeros( evals.shape, evals.dtype )
        for i in orderInds[self.nGaugeParams:]: 
            invEvals[i] = 1.0/evals[i]
        #print "nGaugeParams = ",self.nGaugeParams; print invEvals #DEBUG

          #re-construct "inverted" quadratic form
        invDiagQuadcForm = _np.diag( invEvals )
        self.invRegionQuadcForm = _np.dot(U, _np.dot(invDiagQuadcForm, Udag))
        self.U, self.Udag = U, Udag

        #Store params and offsets of gateset for future use
        self.gateset_paramFlags = gates, G0, SPAM ,SP0
        self.gateset_offsets = gateset.get_vector_offsets(gates,G0,SPAM,SP0)

        #Store list of profile-likelihood confidence intervals
        #  which == sqrt(diagonal els) of invRegionQuadcForm
        self.profLCI = [ _np.sqrt(abs(self.invRegionQuadcForm[k,k])) for k in range(len(evals))]
        self.profLCI = _np.array( self.profLCI, 'd' )

        self.gateset = gateset
        self.level = confidenceLevel #a percentage, i.e. btwn 0 and 100


        #DEBUG
        #print "DEBUG HESSIAN:"
        #print "shape = ",hessian.shape
        #print "nGaugeParams = ",self.nGaugeParams
        #print "nNonGaugeParams = ",self.nNonGaugeParams
        ##print "Eval,InvEval = ",zip(evals,invEvals)
        #N = self.regionQuadcForm.shape[0]
        ##diagEls = [ self.regionQuadcForm[k,k] for k in range(N) ]
        #invdiagEls = sorted([ abs(self.invRegionQuadcForm[k,k]) for k in range(N) ])
        #evals = sorted( _np.abs(_np.linalg.eigvals( self.regionQuadcForm )) )
        #invEvals = sorted( _np.abs(_np.linalg.eigvals( self.invRegionQuadcForm )) )
        #print "index  sorted(abs(inv-diag))     sorted(eigenval)    sorted(inv-eigenval):"
        #for i,(invDiag,eigenval,invev) in enumerate(zip(invdiagEls,evals,invEvals)):
        #    print "%d %15g %15g %15g" % (i,invDiag,eigenval,invev)
        #
        #import sys
        #sys.exit()

    def get_gateset(self):
        """ 
        Retrieve the associated gate set.

        Returns
        -------
        GateSet
            the gate set marking the center location of this confidence region. 
        """
        return self.gateset

    def get_parameterization_flags(self):
        """ 
        Retrieve the quantities specifying gate set parameterization.

        Returns
        -------
        tuple
           (gates,G0,SPAM,SP0) parameters.
        """
        return self.gateset_paramFlags

    def get_profile_likelihood_confidence_intervals(self, label=None):
        """
        Retrieve the profile-likelihood confidence intervals for a specified
        gate set object (or all such intervals).

        Parameters
        ----------
        label : string, optional
            If not None, can be either a gate label, "rho<number>", or "E<number>",
            to specify the confidence intervals corresponding to gate, rhoVec,
            or EVec parameters respectively.  If None, then intervals corresponding
            to all of the gateset's parameters are returned.
            
        Returns
        -------
        numpy array
            One-dimensional array of (positive) interval half-widths which specify
            a symmetric confidence interval.
        """
        if label is None:
            return self.profLCI
        else:
            start,end = self.gateset_offsets[label]
            return self.profLCI[start:end]

    def get_gate_fn_confidence_interval(self, fnOfGate, gateLabel, eps=1e-7, returnFnVal=False, verbosity=0):
        """
        Compute the confidence interval for a function of a single gate.

        Parameters
        ----------
        fnOfGate : function
            A function which takes as its only argument a gate matrix.  The
            returned confidence interval is based on linearizing this function
            and propagating the gateset-space confidence region.

        gateLabel : string
            The label specifying which gate to use in evaluations of fnOfGate.

        eps : float, optional
            Step size used when taking finite-difference derivatives of fnOfGate.

        returnFnVal : bool, optional
            If True, return the value of fnOfGate along with it's confidence
            region half-widths.

        verbosity : int, optional
            Specifies level of detail in standard output.

        Returns
        -------
        df : float or numpy array
            Half-widths of confidence intervals for each of the elements
            in the float or array returned by fnOfGate.  Thus, shape of
            df matches that returned by fnOfGate.

        f0 : float or numpy array
            Only returned when returnFnVal == True. Value of fnOfGate
            at the gate specified by gateLabel.
        """

        gates,G0,SPAM,SP0 = self.get_parameterization_flags()
        nParams = self.gateset.num_params(gates,G0,SPAM,SP0)

        gateMx = self.gateset[gateLabel]
        gateObj = self.gateset.get_gate(gateLabel).copy() # copy because we add eps to this gate
        gpo = self.gateset_offsets[gateLabel][0] #starting "gate parameter offset"        

        f0 = fnOfGate(gateMx) #function value at "base point" gateMx
        nGateParams = gateObj.num_params(G0)
        gateVec0 = gateObj.to_vector(G0)

        #Get finite difference derivative gradF that is shape (nParams, <shape of f0>)
        if type(f0) == float:
            gradF = _np.zeros( nParams, 'd' ) #assume all functions are real-valued for now...
        else:
            gradSize = (nParams,) + tuple(f0.shape)
            gradF = _np.zeros( gradSize, f0.dtype ) #assume all functions are real-valued for now...

        if gates == True or (type(gates) in (list,tuple) and gateLabel in gates):
            for i in range(nGateParams):
                gateVec = gateVec0.copy(); gateVec[i] += eps; gateObj.from_vector(gateVec,G0)
                gradF[gpo + i] = ( fnOfGate( gateObj.matrix ) - f0 ) / eps        
            
        return self._compute_df_from_gradF(gradF, f0, returnFnVal, verbosity)


    def get_gateset_fn_confidence_interval(self, fnOfGateset, eps=1e-7, returnFnVal=False, verbosity=0):
        """
        Compute the confidence interval for a function of a GateSet.

        Parameters
        ----------
        fnOfGateset : function
            A function which takes as its only argument a GateSet object.  The
            returned confidence interval is based on linearizing this function
            and propagating the gateset-space confidence region.

        eps : float, optional
            Step size used when taking finite-difference derivatives of fnOfGateset.

        returnFnVal : bool, optional
            If True, return the value of fnOfGateset along with it's confidence
            region half-widths.

        verbosity : int, optional
            Specifies level of detail in standard output.

        Returns
        -------
        df : float or numpy array
            Half-widths of confidence intervals for each of the elements
            in the float or array returned by fnOfGateset.  Thus, shape of
            df matches that returned by fnOfGateset.

        f0 : float or numpy array
            Only returned when returnFnVal == True. Value of fnOfGateset
            at the gate specified by gateLabel.
        """

        gates,G0,SPAM,SP0 = self.get_parameterization_flags()
        nParams = self.gateset.num_params(gates,G0,SPAM,SP0)

        gateset = self.gateset.copy() # copy because we add eps to this gateset

        f0 = fnOfGateset(gateset) #function value at "base point" gateMx
        gatesetVec0 = gateset.to_vector(gates, G0, SPAM, SP0)
        assert(len(gatesetVec0) == nParams)

        #Get finite difference derivative gradF that is shape (nParams, <shape of f0>)
        if type(f0) == float:
            gradF = _np.zeros( nParams, 'd' ) #assume all functions are real-valued for now...
        else:
            gradSize = (nParams,) + tuple(f0.shape)
            gradF = _np.zeros( gradSize, f0.dtype ) #assume all functions are real-valued for now...

        for i in range(nParams):
            gatesetVec = gatesetVec0.copy(); gatesetVec[i] += eps
            gateset.from_vector(gatesetVec,gates,G0,SPAM,SP0)
            gradF[i] = ( fnOfGateset(gateset) - f0 ) / eps        
            
        return self._compute_df_from_gradF(gradF, f0, returnFnVal, verbosity)


    def get_spam_fn_confidence_interval(self, fnOfSpamVecs, eps=1e-7, returnFnVal=False, verbosity=0):
        """
        Compute the confidence interval for a function of spam vectors.

        Parameters
        ----------
        fnOfSpamVecs : function
            A function which takes two arguments, rhoVecs and EVecs, each of which
            is a list of column vectors.  Note that the EVecs list will include
            *all* the effect vectors, including the a "compliment" vector.  The
            returned confidence interval is based on linearizing this function
            and propagating the gateset-space confidence region.

        eps : float, optional
            Step size used when taking finite-difference derivatives of fnOfSpamVecs.

        returnFnVal : bool, optional
            If True, return the value of fnOfSpamVecs along with it's confidence
            region half-widths.

        verbosity : int, optional
            Specifies level of detail in standard output.

        Returns
        -------
        df : float or numpy array
            Half-widths of confidence intervals for each of the elements
            in the float or array returned by fnOfSpamVecs.  Thus, shape of
            df matches that returned by fnOfSpamVecs.

        f0 : float or numpy array
            Only returned when returnFnVal == True. Value of fnOfSpamVecs.
        """
        gates,G0,SPAM,SP0 = self.get_parameterization_flags()
        nParams = self.gateset.num_params(gates,G0,SPAM,SP0)

        f0 = fnOfSpamVecs(self.gateset.get_rhovecs(), self.gateset.get_evecs())
          #Note: .get_Evecs() can be different from .EVecs b/c the former includes compliment EVec

        #Get finite difference derivative gradF that is shape (nParams, <shape of f0>)
        if type(f0) == float:
            gradF = _np.zeros( nParams, 'd' ) #assume all functions are real-valued for now...
        else:
            gradSize = (nParams,) + tuple(f0.shape)
            gradF = _np.zeros( gradSize, f0.dtype ) #assume all functions are real-valued for now...

        if SPAM: #if not including SPAM vecs in parameterization, then leave grad as all zeros

            gsEps = self.gateset.copy()

            #loop just over parameterized objects - don't use get_rhovecs() here...
            for k,rhoVec in enumerate(self.gateset.rhoVecs): 
                nRhoParams = len(rhoVec) if SP0 else len(rhoVec)-1 # LATER: rhoVecObj.num_params(SP0?)
                m = 0 if SP0 else 1
                off = self.gateset_offsets["rho%d" % k][0]
                for i in range(nRhoParams):
                    vecEps = rhoVec.copy(); vecEps[m+i] += eps; gsEps.set_rhovec( vecEps, k ) #update gsEps parameter
                    gradF[off + i] = ( fnOfSpamVecs( gsEps.get_rhovecs(), gsEps.get_evecs() ) - f0 ) / eps        
                gsEps.set_rhovec( rhoVec.copy(), k )  #I don't think copy() is needed here, but just to be safe

            #loop just over parameterized objects - don't use get_evecs() here...
            for k,EVec in enumerate(self.gateset.EVecs): 
                nEParams = len(EVec) # LATER: EVecObj.num_params()
                off = self.gateset_offsets["E%d" % k][0]
                for i in range(nEParams):
                    vecEps = EVec.copy(); vecEps[i] += eps; gsEps.set_evec( vecEps, k ) #update gsEps parameter
                    gradF[off + i] = ( fnOfSpamVecs( gsEps.get_rhovecs(), gsEps.get_evecs() ) - f0 ) / eps        
                gsEps.set_evec( EVec.copy(), k )  #I don't think copy() is needed here, but just to be safe

        return self._compute_df_from_gradF(gradF, f0, returnFnVal, verbosity)


    def _compute_df_from_gradF(self, gradF, f0, returnFnVal, verbosity):
        """ 
        Internal function which computes error bars given an function value
        and gradient (using linear approx. to function)
        """
    
        #Compute df = sqrt( gradFu.dag * 1/D * gradFu )
        #  where regionQuadcForm = U * D * U.dag and gradFu = U.dag * gradF
        #  so df = sqrt( gradF.dag * U * 1/D * U.dag * gradF )
        #        = sqrt( gradF.dag * invRegionQuadcForm * gradF )

        if verbosity > 0:
            print "gradF = ",gradF

        if type(f0) == float:
            gradFdag = _np.conjugate(_np.transpose(gradF))

            #DEBUG
            #arg = _np.dot(gradFdag, _np.dot(self.invRegionQuadcForm, gradF))
            #print "HERE: taking sqrt(abs(%s))" % arg

            df = _np.sqrt( abs(_np.dot(gradFdag, _np.dot(self.invRegionQuadcForm, gradF))) )
        else:
            fDims = len(f0.shape)
            gradF = _np.rollaxis(gradF, 0, 1+fDims) # roll parameter axis to be the last index, preceded by f-shape
            df = _np.empty( f0.shape, f0.dtype)

            if f0.dtype == _np.dtype("complex"): #real and imaginary parts separately
                if fDims == 0: #same as float case above
                    gradFdag = _np.transpose(gradF)
                    df = _np.sqrt( abs( _np.dot(gradFdag.real, _np.dot(self.invRegionQuadcForm, gradF.real))) ) \
                        + 1j * _np.sqrt( abs( _np.dot(gradFdag.imag, _np.dot(self.invRegionQuadcForm, gradF.imag))) )
                elif fDims == 1:
                    for i in range(f0.shape[0]):
                        gradFdag = _np.transpose(gradF[i])
                        df[i] = _np.sqrt( abs( _np.dot(gradFdag.real, _np.dot(self.invRegionQuadcForm, gradF[i].real))) ) \
                            + 1j * _np.sqrt( abs( _np.dot(gradFdag.imag, _np.dot(self.invRegionQuadcForm, gradF[i].imag))) )
                elif fDims == 2:
                    for i in range(f0.shape[0]):
                        for j in range(f0.shape[1]):
                            gradFdag = _np.transpose(gradF[i,j])
                            df[i,j] = _np.sqrt( abs( _np.dot(gradFdag.real, _np.dot(self.invRegionQuadcForm, gradF[i,j].real))) ) \
                                + 1j * _np.sqrt( abs( _np.dot(gradFdag.imag, _np.dot(self.invRegionQuadcForm, gradF[i,j].imag))) )
                else:
                    raise ValueError("Unsupported number of dimensions returned by fnOfGate or fnOfGateset: %d" % fDims)
    
            else: #assume real -- so really don't need conjugate calls below
                if fDims == 0: #same as float case above
                    gradFdag = _np.conjugate(_np.transpose(gradF))

                    #DEBUG
                    #arg = _np.dot(gradFdag, _np.dot(self.invRegionQuadcForm, gradF))
                    #print "HERE2: taking sqrt(abs(%s))" % arg

                    df = _np.sqrt( abs( _np.dot(gradFdag, _np.dot(self.invRegionQuadcForm, gradF))) )
                elif fDims == 1:
                    for i in range(f0.shape[0]):
                        gradFdag = _np.conjugate(_np.transpose(gradF[i]))
                        df[i] = _np.sqrt( abs(_np.dot(gradFdag, _np.dot(self.invRegionQuadcForm, gradF[i]))) )
                elif fDims == 2:
                    for i in range(f0.shape[0]):
                        for j in range(f0.shape[1]):
                            gradFdag = _np.conjugate(_np.transpose(gradF[i,j]))
                            df[i,j] = _np.sqrt( abs(_np.dot(gradFdag, _np.dot(self.invRegionQuadcForm, gradF[i,j]))) )
                else:
                    raise ValueError("Unsupported number of dimensions returned by fnOfGate or fnOfGateset: %d" % fDims)
        
        if verbosity > 0:
            print "df = ",df
        
        return (df, f0 ) if returnFnVal else df




def _optProjectionForGateCIs(gateset, base_hessian, nNonGaugeParams, nGaugeParams,
                             gates, G0, SPAM, SP0, level, verbosity = 0):

    #Params (make into args?)
    method = "L-BFGS-B"
    maxiter = 10000
    maxfev = 10000
    tol = 1e-6

    if verbosity > 2: print ""
    if verbosity > 1: print "--- Hessian Projector Optimization for gate CIs (%s) ---" % method

    def objective_func(vectorM):
        matM = vectorM.reshape( (nNonGaugeParams,nGaugeParams) )
        proj_extra = gateset.get_nongauge_projector(matM, gates, G0, SPAM, SP0)
        projected_hessian_ex = _np.dot(proj_extra, _np.dot(base_hessian, proj_extra))
         
        ci = ConfidenceRegion(gateset, projected_hessian_ex, level, gates, G0, SPAM, SP0, hessianProjection="none")
        gateCIs = _np.concatenate( [ ci.get_profile_likelihood_confidence_intervals(gl).flatten() for gl in gateset] )
        return _np.sqrt( _np.sum(gateCIs**2) )
                    
    #Run Minimization Algorithm
    startM = _np.zeros( (nNonGaugeParams,nGaugeParams), 'd')  
    x0 = startM.flatten()
    print_obj_func = _opt.create_obj_func_printer(objective_func)
    minSol = _opt.minimize(objective_func, x0,
                                    method=method, maxiter=maxiter,
                                    maxfev=maxfev, tol=tol, 
                                    callback = print_obj_func if verbosity > 2 else None)

    mixMx = minSol.x.reshape( (nNonGaugeParams,nGaugeParams) )
    proj_extra = gateset.get_nongauge_projector(mixMx, gates, G0, SPAM, SP0)
    projected_hessian_ex = _np.dot(proj_extra, _np.dot(base_hessian, proj_extra))
         
    if verbosity > 1:
        print 'The resulting min sqrt(sum(gateCIs**2)): %g' % minSol.fun
        
    return projected_hessian_ex


#OLD

##chi2, dchi2, HessD['perfect'] = GST.AT.chi2(DSD['perfect'],gsEst,lsgstLists[-1],
##                                         returnGradient=True,returnHessian=True)
## semilogy(sort(abs(np.linalg.eigvals(ProjNoGauge * np.matrix(HessD['perfect']) * ProjNoGauge))),'+')
#def gateset_confidence_region(gateset, chi2Hessian, gates=True,G0=True,SPAM=True,SP0=True):
#    proj_non_gauge = gateset.get_nongauge_projector(gates,G0,SPAM,SP0)
#    return _np.dot(proj_non_gauge, _np.dot(chi2Hessian, proj_non_gauge))
#
#    # semilogy(sort(abs(np.linalg.eigvals(ProjNoGauge * np.matrix(HessD['perfect']) * ProjNoGauge))),'+')
#    
#    #Next: chi2Funct or totalchi2, which can compute its Hessian also, should be able to project
#    # (or create another function to do so) this Hessian to the non-gauge space (it should be ~zero
#    # on the gauge space)
#    # HERE TODO: create some function to compute error bars for a particular estimate (GateSet,Chi2Hessian) & propagate?
