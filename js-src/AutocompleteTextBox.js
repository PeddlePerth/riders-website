const { useState, useEffect, useMemo, useRef } = require('react');

const AutocompleteTextBoxV2 = ({ items=[], onSelect, onBlur, initialFocus=true, titleAttr="title", className, selectedItem }) => {
    const [text, setText] = useState(selectedItem ? selectedItem[titleAttr] : '');
    const [showResults, setShowResults] = useState(initialFocus);
    const inputEl = useRef(null);

    const results = useMemo(() => {
        if (text.length < 1) return items;
        let compare = text.toLowerCase();
        return items.filter(itm => {
            let itmText = itm[titleAttr];
            if (!itmText) return false;
            return itm[titleAttr].toLowerCase().startsWith(compare);
        });
    }, [items, text]);

    useEffect(() => {
        if (inputEl.current && !selectedItem && showResults)
            inputEl.current.focus();
    }, [selectedItem, showResults]);

    function select(itm) {
        var clearSelection = onSelect(itm);
        setShowResults(false);

        if (clearSelection) { // parent component must also set selectedItem=null otherwise weird things may happen
            setText('');
        } else if (itm) {
            setText(itm[titleAttr]);
        }
    }

    return (
    <form autoComplete="off" className={"acb-container" + (className ? ' ' + className : '') + (selectedItem ? ' selected' : '')}
        onSubmit={(e) => {
            e.preventDefault();
            setShowResults(false);
            if (results.length == 1) select(results[0]);
        }}>
        <input type="text" name="q" id="q" value={text}
            onChange={(e) => {
                setText(e.target.value); 
                if (selectedItem) onSelect(null);
                setShowResults(true); 
            }}
            onBlur={() => {
                setShowResults(false);
                if (onBlur) onBlur();
            }}
            onKeyDown={(e) => {
                if (e.key == 'Tab' && results.length == 1 && !selectedItem) { // TAB key pressed
                    e.preventDefault();
                    setShowResults(false);
                    select(results[0]);
                }
            }}
            onFocus={() => setShowResults(true)}
            onClick={() => setShowResults(true)}
            ref={inputEl}/>
        { (!selectedItem && showResults) ? 
        <ul className="acb-results-list">
                { results.map((itm, i) => 
                <li key={i} className="acb-results-item"
                    onMouseDown={(e) => {
                        select(itm);
                        e.preventDefault();
                    }}>
                    { itm[titleAttr] }
                </li>)}
        </ul> : null}
    </form>);
};

module.exports = { AutocompleteTextBoxV2 };