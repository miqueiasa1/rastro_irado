import { useState, useEffect, useCallback, useRef } from "react";
import GEX_LEVELS, { getGexLevels } from "../gexLevels";
import { toLocalTime } from "../utils/time";

const FIREBASE_URL = import.meta.env.VITE_FIREBASE_URL;
const API = FIREBASE_URL ? null : 'http://localhost:8888';

const padSeriesToFullDay = (series, isB3 = false, timeframe = 'M5') => {
  if (!series || series.length === 0) return series;

  const lastTimeStr = series[series.length - 1].time; // ex: "18:05"
  if (!lastTimeStr) return series;

  const [hStr, mStr] = lastTimeStr.split(":");
  let currentH = parseInt(hStr, 10);
  let currentM = parseInt(mStr, 10);

  const padded = [...series];

  let stepMinutes = 5;
  if (timeframe === 'M1') stepMinutes = 1;
  else if (timeframe === 'M2') stepMinutes = 2;
  else if (timeframe === 'M5') stepMinutes = 5;
  else if (timeframe === 'M15') stepMinutes = 15;
  else if (timeframe === 'M30') stepMinutes = 30;
  else if (timeframe === 'H1') stepMinutes = 60;

  let targetEndH = isB3 ? 0 : 23;
  let targetEndM = isB3 ? 30 : 59;
  
  if (timeframe === 'H1') {
    targetEndM = 0;
    if (isB3) targetEndH = 0;
  } else if (timeframe === 'M30') {
    targetEndM = 30;
  } else if (timeframe === 'M15') {
    targetEndM = 45;
  }

  const maxPaddedLength = series.length + Math.ceil(24 * 60 / stepMinutes);

  while (true) {
    if (currentH === targetEndH && currentM >= targetEndM) break;
    if (padded.length > maxPaddedLength) break; 

    currentM += stepMinutes;
    if (currentM >= 60) {
      currentH = (currentH + Math.floor(currentM / 60)) % 24;
      currentM = currentM % 60;
    }

    const h = currentH.toString().padStart(2, '0');
    const m = currentM.toString().padStart(2, '0');
    const timeTickmill = `${h}:${m}`;

    padded.push({
      time: timeTickmill,
      time_local: isB3 ? toLocalTime(timeTickmill, -6) : null
    });
  }
  return padded;
};

export function useIraiData({ selectedTarget, liveMode, timeframe }) {
  const [dates, setDates] = useState([]);
  const [selectedDate, setSelectedDate] = useState(null);
  const [targetsMeta, setTargetsMeta] = useState([]);
  const [seriesInfo, setSeriesInfo] = useState({});
  const [series, setSeries] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  
  const [gexWalls, setGexWalls] = useState([]);
  const [availableRuns, setAvailableRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [garchData, setGarchData] = useState(null);
  
  const isFirstLoadRef = useRef(true);

  const effectiveDate = liveMode ? (dates.length > 0 ? dates[0] : selectedDate) : selectedDate;

  // Fetch dates once on mount (and poll every 60s/120s)
  useEffect(() => {
    function loadDates() {
      if (FIREBASE_URL) {
        const baseUrl = FIREBASE_URL.replace(/\.json$/, '').replace(/\/$/, '');
        fetch(`${baseUrl}/dates.json`)
          .then(r => r.json())
          .then(data => {
            const d = data?.dates || [];
            setDates(d);
            if (d.length > 0) setSelectedDate(prev => prev || d[0]);
          })
          .catch(e => setError(e.message));
      } else {
        fetch(`${API}/api/irai/dates`)
          .then(r => r.json())
          .then(data => {
            const d = data.dates || [];
            setDates(d);
            if (d.length > 0) setSelectedDate(prev => prev || d[0]);
          })
          .catch(e => setError(e.message));
      }
    }
    loadDates();
    const poll = setInterval(loadDates, FIREBASE_URL ? 120_000 : 60_000);
    return () => clearInterval(poll);
  }, []);

  // Fetch targets once on mount
  useEffect(() => {
    if (FIREBASE_URL) {
      const baseUrl = FIREBASE_URL.replace(/\.json$/, '').replace(/\/$/, '');
      fetch(`${baseUrl}/targets.json`)
        .then(r => r.json())
        .then(data => setTargetsMeta((data?.targets || []).filter(t => t.calibrated)))
        .catch(() => { });
    } else {
      fetch(`${API}/api/irai/targets`)
        .then(r => r.json())
        .then(data => setTargetsMeta((data.targets || []).filter(t => t.calibrated)))
        .catch(() => { });
    }
  }, []);

  // Fetch series data
  const fetchSeries = useCallback((date, target, silent = false) => {
    if (!date) return;
    if (!silent) {
      setLoading(true);
      setSeries([]);
      setSummary(null);
      setSeriesInfo({});
      setError(null);
    }

    if (FIREBASE_URL) {
      const baseUrl = FIREBASE_URL.replace(/\.json$/, '').replace(/\/$/, '');
      const safeTarget = target.replace('$', '_').replace('.', '_');
      
      const fetches = [
        fetch(`${baseUrl}/series/${safeTarget}.json`).then(r => r.json()),
        fetch(`${baseUrl}/summaries/${safeTarget}.json`).then(r => r.json()),
        fetch(`${baseUrl}/history/${safeTarget}.json`).then(r => r.json()),
        fetch(`${baseUrl}/garch/${safeTarget}.json`).then(r => r.json()).catch(() => null)
      ];
      
      const shouldFetchLastUpdate = silent || isFirstLoadRef.current;
      if (shouldFetchLastUpdate) {
        isFirstLoadRef.current = false;
        fetches.push(fetch(`${baseUrl}/last_update.json`).then(r => r.json()).catch(() => null));
      }

      Promise.all(fetches)
        .then(([seriesData, summariesData, historyData, garchDataRes, lastUpdateData]) => {
          const tMeta = targetsMeta.find(t => t.target === target) || {};
          const s = seriesData || [];
          const sum = summariesData || {};
          const history_closes = historyData || [];

          const isB3 = tMeta.session_start_h && tMeta.session_start_h !== 0;
          const processed = s.map(x => {
            const timeDb = x.timestamp ? x.timestamp.substring(11, 16) : '00:00';
            const timeTickmill = timeDb;
            const timeBrt = isB3 ? toLocalTime(timeDb, -6) : null;
            return {
              ...x,
              time: timeTickmill,
              time_local: timeBrt,
            };
          });

          let sliced = processed;
          if (isB3) {
            sliced = processed.filter(s => {
              if (!s.time) return true;
              return s.time >= "09:00";
            });
            if (sliced.length === 0) sliced = processed;
          }

          setSeries(padSeriesToFullDay(sliced, isB3, timeframe));
          setSummary(sum);
          setSeriesInfo({ 
            display_name: tMeta.display_name, 
            icon: tMeta.icon, 
            history_closes, 
            tz_offset: isB3 ? -3 : 0, 
            tz_label: 'BRT',
            accuracy: sum?.accuracy,
            divergence_threshold: tMeta.divergence_config?.threshold || 2.0
          });
          setGexWalls(getGexLevels(target));
          setAvailableRuns([]);
          setSelectedRun(null);
          const finalGarch = (sum && sum.garch && Array.isArray(sum.garch.history)) ? sum.garch : ((garchDataRes && Array.isArray(garchDataRes.history)) ? garchDataRes : null);
          setGarchData(finalGarch);
          setLoading(false);
          if (shouldFetchLastUpdate && lastUpdateData !== undefined && lastUpdateData !== null) {
            setLastUpdate(new Date(lastUpdateData * 1000));
          }
          setError(null);
        })
        .catch(e => { setError(e.message); setLoading(false); });
    } else {
      const seriesPromise = fetch(`${API}/api/irai/series?session_date=${date}&target=${encodeURIComponent(target)}&version=v2&timeframe=${timeframe}`).then(r => r.json());
      const gexPromise = fetch(`${API}/api/gex?target=${encodeURIComponent(target)}&date=${date}`).then(r => r.json()).catch(() => null);
      const garchPromise = fetch(`${API}/api/garch?symbol=${encodeURIComponent(target === 'WIN$N' ? 'IBOV' : target)}&date=${date}`).then(r => r.json()).catch(() => null);

      Promise.all([seriesPromise, gexPromise, garchPromise])
        .then(([data, gexData, garchRes]) => {
          if (data.error) { setError(data.error); setLoading(false); return; }
          const isB3 = data.is_b3 || false;
          const processed = (data.series || []).map(s => {
            const timeDb = s.timestamp ? s.timestamp.substring(11, 16) : '00:00';
            const timeTickmill = timeDb;
            const timeBrt = isB3 ? toLocalTime(timeDb, -6) : null;
            return {
              ...s,
              time: timeTickmill,
              time_local: timeBrt,
            };
          });
          let sliced = processed;
          if (isB3) {
            sliced = processed.filter(s => {
              if (!s.time) return true;
              return s.time >= "09:00";
            });
            if (sliced.length === 0) sliced = processed; // fallback
          }

          setSeries(padSeriesToFullDay(sliced, isB3, timeframe));
          setSummary(data.summary);
          setSeriesInfo({ 
            display_name: data.display_name, 
            icon: data.icon, 
            history_closes: data.history_closes || [], 
            tz_offset: isB3 ? -3 : 0, 
            tz_label: 'BRT', 
            accuracy: data.summary?.accuracy,
            divergence_threshold: data.divergence_threshold || 2.0
          });
          
          if (gexData && Array.isArray(gexData.levels) && gexData.levels.length > 0) {
            setGexWalls(gexData.levels);
            setAvailableRuns(gexData.available_runs || []);
            setSelectedRun(gexData.selected_run || null);
          } else {
            setGexWalls(getGexLevels(target));
            setAvailableRuns([]);
            setSelectedRun(null);
          }

          if (garchRes && Array.isArray(garchRes.history)) {
            setGarchData(garchRes);
          } else {
            setGarchData(null);
          }

          setLoading(false);
          setLastUpdate(new Date());
          setError(null);
        })
        .catch(e => { setError(e.message); setLoading(false); });
    }
  }, [targetsMeta, timeframe]);

  const fetchGexForRun = useCallback((runName) => {
    if (FIREBASE_URL || !effectiveDate) return;
    fetch(`${API}/api/gex?target=${encodeURIComponent(selectedTarget)}&date=${effectiveDate}&run=${runName}`)
      .then(r => r.json())
      .then(gexData => {
        if (gexData && Array.isArray(gexData.levels)) {
          setGexWalls(gexData.levels);
          setSelectedRun(gexData.selected_run || null);
        }
      })
      .catch(() => {});
  }, [selectedTarget, effectiveDate]);

  // Initial load and polling timer
  useEffect(() => {
    Promise.resolve().then(() => {
      fetchSeries(effectiveDate, selectedTarget, false);
    });

    if (!liveMode) return;

    let mounted = true;
    let pollTimer = null;

    pollTimer = setInterval(() => {
      if (mounted) fetchSeries(effectiveDate, selectedTarget, true);
    }, FIREBASE_URL ? 120_000 : 60_000);
    
    return () => {
      mounted = false;
      if (pollTimer) clearInterval(pollTimer);
    };
  }, [effectiveDate, selectedTarget, liveMode, fetchSeries]);

  return {
    dates,
    selectedDate,
    setSelectedDate,
    effectiveDate,
    targetsMeta,
    series,
    summary,
    loading,
    error,
    lastUpdate,
    gexWalls,
    availableRuns,
    selectedRun,
    garchData,
    seriesInfo,
    fetchGexForRun,
    refetchSeries: () => fetchSeries(effectiveDate, selectedTarget, true)
  };
}
