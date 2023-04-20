const $ = require('jquery');
const { useState, useEffect } = require("react");
const { post_data, format_num } = require("./utils");

// from https://stackoverflow.com/questions/46240647/react-how-to-force-a-function-component-to-render
function useForceUpdate(){
    const [value, setValue] = useState(0); // integer state
    return () => setValue(value => value + 1); // update state to force render
}


// Custom "React hook" function for managing AJAX data retrieval & status
function useAjaxData(
    url, // URL for POSTing the AJAX data in JSON format
    f_getRequestData, // function returning POST request parameters for the next request when one is made
    f_handleResponse, // callback when response is obtained
    f_getInitialParams
) {

    const [error, setError] = useState(null); // error message from failed XHR
    const [data, setData] = useState(null); // data response from last successful XHR

    function sendRequest(dataParams) {
        var handleError = true, xhrComplete = false;
        var xhr = post_data(url, f_getRequestData(data, dataParams), (ok, respData) => {
            xhrComplete = true;
            // the XHR triggering this event was aborted intentionally, simply return and don't touch state
            if (!handleError) return;
            if (f_handleResponse) f_handleResponse(ok, respData);
            if (ok) {
                setData(respData);
                setError(null);
            } else {
                setError('Error loading data: ' + respData);
            }
        });

        return {
            silentlyAbort: () => {
                handleError = false;
                xhr.abort();
            },
            isComplete: () => xhrComplete,
        };
    }

    const [dataParams, setDataParams] = useState(() => f_getInitialParams());
    const [request, setRequest] = useState(() => sendRequest(dataParams)); // reference to current request if one is currently underway

    function reloadData(newDataParams) {
        if (newDataParams !== undefined) setDataParams(newDataParams);
        setRequest((prevRequest) => {
            if (prevRequest) prevRequest.silentlyAbort();
            return sendRequest(newDataParams || dataParams);
        })
    }

    var isLoading = request && !request.isComplete();
    //console.log('dataParams', dataParams);

    return [data, isLoading, error, dataParams, reloadData];
}

const LOCK_POLL_INTERVAL = 30*1000; // every 30seconds

function useEditableAjaxData(
    dataUrl,
    lockUrl,
    autosaveTimeout,
    f_getRequestData, // (currentData, dataParams, isSave) => returns JSON data for request to server
    f_getLockData, // (dataParams) => returns {page, date}
    f_handleResponse,
    f_getInitialParams, // returns initial dataparams
) {
    const [currentData, setCurrentData] = useState(null); // in-memory copy of data which contains any edits made by the user
    const [dataParams, setDataParams] = useState(() => f_getInitialParams());
    const [error, setError] = useState(null);

    const [timerId, setTimerId] = useState(null); // timer number from window.setTimeout()
    const [lastEditTime, setLastEditTime] = useState(new Date()); // time when last user edit was made
    const [lastSaveTime, setLastSaveTime] = useState(new Date()); // time when data was last saved/loaded from server successfully
    const [hasDataLock, setHasDataLock] = useState(false);

    // locking mechanics
    function pollDataLock() {
        var timer = null;
        var polling = false;
        var xhr = null;
        var lockTime = null; // null until/if we get the lock
        if (window.sessionStorage.getItem('lockTime_' + window.page_name)) {
            lockTime = parseInt(window.sessionStorage.getItem('lockTime' + window.page_name));
        }
        var myState;
        
        const doPoll = (forceAcquire, releaseLock) => {
            xhr = post_data(lockUrl, {
                ...f_getLockData(dataParams), // must return {date}
                page: window.page_name,
                force: forceAcquire,
                releaseLock: releaseLock,
                lockTime: lockTime,
            }, (ok, respData) => {
                if (!ok || releaseLock) return;
                myState.onLockResponse(false, respData, releaseLock);
            });
        }

        const stopPoll = () => {
            polling = false;
            window.clearTimeout(timer);
            if (xhr) xhr.abort();
        };

        const resetPoll = () => {
            stopPoll();
            polling = true;
            timer = window.setTimeout(() => {
                if (!polling) return;
                myState.doPoll(false, false);
            }, LOCK_POLL_INTERVAL);
        };

        function onLockResponse(isSave, respData, releaseLock) {
            if (respData == null) {
                setError('Error acquiring data lock: Edits may not be saved! Please reload to try again.');
                return false;
            }
            if (releaseLock)
                return false; // nothing to do
            if (respData.success) {
                myState.setLockTime(respData.time);
                myState.resetPoll();
                setHasDataLock(true);
                return false;
            } else {
                let lastseen =  format_num(((new Date()).valueOf() - respData.prevTime) / 1000, 0, 0, 0);
                var force = false;
                let _lockTime = lockTime;
                myState.setLockTime(null);
                setHasDataLock(false);
                myState.stopPoll();

                if (_lockTime != null) {
                    // we had the lock before
                    //force = confirm( Kick them off and overwrite their changes?`);
                    alert(`Warning: ${respData.prevUser} has taken over editing (last seen ${lastseen} seconds ago). Reload the page to avoid data loss.`);
                } else if (_lockTime == null) {
                    // we didn't have the lock ever
                    if (isSave) {
                        force = confirm(`${respData.prevUser} is currently editing this page (last seen ${lastseen} seconds ago). Overwrite their changes?`);
                    } else {
                        force = confirm(`${respData.prevUser} is currently editing this page (last seen ${lastseen} seconds ago). Take over editing?`);
                    }
                }
                return force;
            }
        }

        resetPoll();

        myState = { doPoll, resetPoll, stopPoll, onLockResponse,
            getLockTime: () => lockTime,
            setLockTime: (t) => {
                lockTime = t;
                if (lockTime) {
                    window.sessionStorage.setItem('lockTime_' + window.page_name, lockTime.valueOf().toString());
                } else {
                    window.sessionStorage.removeItem('lockTime_' + window.page_name);
                }
            },
        };
        return myState;
    }

    // hack to produce an effect with accessible state
    const [pollLock, setPollLock] = useState(() => pollDataLock());
    useEffect(() => {
        return () => {
            pollLock.stopPoll();
            pollLock.doPoll(false, true); // release lock when editor component unmounted
        };
    }, []);


    // if data is saved: any edits made between the save time and the load time of the response must not be discarded
    // ie. if any edits are made between save-request and save-response then the save-response-data must be ignored
    function sendRequest(isSave, dataParams, forceLock, releaseLock) { // use a closure to preserve additional state relating to the XHR request
        var handleError = true; // flag to prevent error callback from intentional abort of request in progress
        var isComplete = false; // flag to record whether request complete callback has fired
        var xhr = null;

        function doRequest(forceLock, releaseLock) {
            pollLock.resetPoll();
            xhr = post_data(dataUrl, {
                ...f_getRequestData(currentData, dataParams, isSave),
                lockData: {
                    ...f_getLockData(dataParams), // must return {date}
                    lockTime: pollLock.getLockTime(),
                    //releaseLock: false,
                    force: forceLock,
                },
            }, (ok, respData) => {
                isComplete = true;
                if (!handleError) {
                    // the XHR triggering this event was aborted intentionally, simply return and don't touch state
                    return;
                }
                if (ok) {
                    if (respData) {
                        let retryLockForce = pollLock.onLockResponse(isSave, respData.lockData);
                        if (retryLockForce) {
                            // if we are going to retry the lock, discard the rest of respData and send a new request
                            // since it will have ignored our changes
                            isComplete = false;
                            doRequest(true, false);
                            return;
                        }
                    }
                    setCurrentData(respData);
                    setLastSaveTime(new Date());
                    setError(null);
                } else {
                    setError(`Error ${isSave ? 'saving' : 'loading'} data: ${respData}`);
                }
                if (f_handleResponse) f_handleResponse(ok, respData);
            });
        }

        doRequest(false, false);

        return {
            silentlyAbort: () => {
                handleError = false;
                xhr.abort();
            },
            isComplete: () => isComplete,
        };
    }

    // current request state: single object to prevent side effects from multiple setState calls
    const [currentRequest, setCurrentRequest] = useState(() => sendRequest(false, dataParams));
    // Note: component unmounting while request is in-progress may result in errors and/or memory leaks
    // ie. calls to setState() after component is unmounted
    useEffect(() => () => {
        if (currentRequest) currentRequest.silentlyAbort();
    }, []);
    // empty list triggers effect only on mount/unmount: see https://stackoverflow.com/questions/55020041/react-hooks-useeffect-cleanup-for-only-componentwillunmount

    function makeRequest(isSave, dataParams) {
        //console.error('makeRequest', action, dataParams);
        setDataParams(dataParams);
        setCurrentRequest((prevRequest) => {
            if (prevRequest) prevRequest.silentlyAbort();
            return sendRequest(isSave, dataParams);
        });
    }
    const save = (dataParams) => makeRequest(true, dataParams);
    const reload = (dataParams) => makeRequest(false, dataParams);

    useEffect(() => {
        // Great article at https://www.igvita.com/2015/11/20/dont-lose-user-and-app-state-use-page-visibility/
        function onBeforeUnload(event) {
            if (lastEditTime.valueOf() > lastSaveTime.valueOf()) {
                event.preventDefault();
                let msg = "There is unsaved data on the page! Are you sure you want to leave?";
                event.returnValue = msg;
                if (pollLock.getLockTime() !== null) pollLock.doPoll(false, true); // release lock if we can
                return msg;
            }
        }

        function onVisibilityChange(event) {
            if (document.visibilityState == 'hidden') {
                pollLock.stopPoll();
                if (pollLock.getLockTime() !== null)
                    pollLock.doPoll(false, true); // release lock
            } else if (document.visibilityState == 'visible') {
                // should really reload data at this point
                if (pollLock.getLockTime() !== null) pollLock.doPoll(false, false);
            }
        }

        document.addEventListener("visibilitychange", onVisibilityChange);

        addEventListener("beforeunload", onBeforeUnload, {capture: true});
        return () => {
            removeEventListener("beforeunload", onBeforeUnload, {capture: true});
            document.removeEventListener("visibilitychange", onVisibilityChange);
        };
    }, [save, reload]);


    function onDataEdit(newDataParams) {
        if (newDataParams !== undefined) {
            setDataParams(newDataParams);
        }
        setLastEditTime(new Date());
        if (currentRequest && !currentRequest.isComplete()) {
            currentRequest.silentlyAbort();
        }
        if (autosaveTimeout != null) {
            if (timerId !== null) window.clearTimeout(timerId);
            setTimerId(window.setTimeout(() => save(newDataParams || dataParams), autosaveTimeout));
        }
    }

    const dataIsConsistent = lastSaveTime.valueOf() >= lastEditTime.valueOf();
    const requestInProgress = currentRequest && !currentRequest.isComplete();

    return [
        currentData,
        dataParams,
        dataIsConsistent,
        requestInProgress,
        error,
        hasDataLock,
        save,
        reload,
        onDataEdit
    ];
}

function useTimeout(
    timeoutMs, // time (ms) since last action until timer is triggered
    autostartTimer, // whether to automatically start the timer
    onTimeout // callback when timer "goes off" (times out)
) {

    const [timerId, setTimerId] = useState(null);
    const [lastResetTime, setLastResetTime] = useState(null); // when the timer was last reset
    const [timedOutTime, setTimedOutTime] = useState(null); // when the timer most recently "went off"

    // reset the timer to occur in another timeoutMs without triggering the callback
    function resetTimer() {
        if (timerId) window.clearTimeout(timerId);
        setLastResetTime((new Date()).valueOf());
        setTimerId(window.setTimeout(timerCallback, timeoutMs));
    }

    function stopTimer() {
        setTimedOutTime(new Date().valueOf());
        setLastResetTime(null);
        if (timerId) window.clearTimeout(timerId);
        setTimerId(null);
    }

    function timerCallback() {
        setTimedOutTime((new Date().valueOf()));
        if (autostartTimer) resetTimer();
        onTimeout();
    }

    const now = (new Date()).valueOf();
    if (timerId === null && ((lastResetTime != null && lastResetTime + timeoutMs > now) || autostartTimer)) {
        resetTimer();
    }

    return [
        timedOutTime != null ? (now - timedOutTime) : null,
        lastResetTime != null ? (now - lastResetTime) : null,
        resetTimer, stopTimer];
}

module.exports = {useAjaxData, useTimeout, useForceUpdate, useEditableAjaxData};