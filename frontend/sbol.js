/* SBOL 3 export. Turns the annotated GenBank text that the engine produces into an SBOL 3 document (RDF, Turtle), so that every
   download of the Builder is available in both formats from one source.

   - One record of the GenBank text (LOCUS ... //) becomes one Component with its Sequence. A file with several records becomes one
     document with several Components.
   - Every GenBank feature becomes a SequenceFeature with its Range location(s), the strand as orientation and a Sequence Ontology role.
   - The Component is an engineered plasmid (circular) or an engineered region (linear).

   Used in the browser (window.ENCORE_SBOL) and in the Node tests (module.exports). Read the result with pySBOL3 or SynBioHub. */
(function(root){
  var NS = 'https://gitlab.igem.org/2026/software/kit/encore-software/sbol/';
  var SO = 'https://identifiers.org/SO:';
  var ROLE = {
    promoter: '0000167', CDS: '0000316', terminator: '0000141', rep_origin: '0000296', primer_bind: '0005850',
    gene: '0000704', misc_binding: '0000409', protein_bind: '0000410', regulatory: '0005836', '5\'UTR': '0000204', '3\'UTR': '0000205',
    misc_feature: '0000001', overhang: '0000001', source: '0000001', sig_peptide: '0000418', mat_peptide: '0000419'
  };
  var SITE_ROLE = '0001687';                                  // restriction enzyme recognition site (labels such as BbsI, BsaI)

  function stripTags(s){ return String(s).replace(/<[^>]*>/g, ''); }
  function lit(s){                                            // Turtle string literal
    return '"' + String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\r?\n/g, '\\n').replace(/\t/g, '\\t') + '"';
  }
  function displayId(name, used){                             // letters, digits and underscore, starting with a letter
    var id = String(name || 'part').replace(/[^A-Za-z0-9_]+/g, '_').replace(/^_+|_+$/g, '') || 'part';
    if (!/^[A-Za-z]/.test(id)) id = 'n' + id;
    var base = id, n = 2;
    while (used[id]) id = base + '_' + (n++);
    used[id] = true;
    return id;
  }

  /* ---- GenBank reading ---- */
  function splitRecords(text){
    var recs = [], cur = null;
    String(text).split(/\r?\n/).forEach(function(line){
      if (/^LOCUS\s/.test(line)) { cur = []; recs.push(cur); }
      if (cur) cur.push(line);
      if (/^\/\/\s*$/.test(line)) cur = null;
    });
    return recs;
  }
  function parseLocation(loc){
    var reverse = false, s = loc.replace(/\s+/g, '');
    var m = s.match(/^complement\((.*)\)$/);
    if (m) { reverse = true; s = m[1]; }
    m = s.match(/^(?:join|order)\((.*)\)$/);
    var parts = m ? m[1].split(',') : [s];
    var ranges = [];
    parts.forEach(function(p){
      var c = false, q = p, mm = q.match(/^complement\((.*)\)$/);
      if (mm) { c = true; q = mm[1]; }
      var r = q.replace(/[<>]/g, '').match(/^(\d+)(?:\.\.(\d+))?$/);
      if (r) ranges.push({ start: +r[1], end: +(r[2] || r[1]), reverse: reverse !== c });
    });
    return ranges;
  }
  function parseRecord(lines){
    var rec = { name: '', circular: false, definition: '', features: [], sequence: '' };
    var locus = lines[0].match(/^LOCUS\s+(\S+)/);
    rec.name = locus ? locus[1] : 'record';
    rec.circular = /\bcircular\b/i.test(lines[0]);
    var i = 1, def = [];
    for (; i < lines.length; i++) {
      var l = lines[i];
      if (/^FEATURES/.test(l) || /^ORIGIN/.test(l)) break;
      if (/^DEFINITION\s/.test(l)) def.push(l.replace(/^DEFINITION\s+/, ''));
      else if (def.length && /^\s{12}\S/.test(l)) def.push(l.trim());
    }
    rec.definition = def.join(' ').trim();
    if (/^FEATURES/.test(lines[i] || '')) {
      i++;
      var feat = null, qual = null;
      for (; i < lines.length; i++) {
        l = lines[i];
        if (/^ORIGIN/.test(l)) break;
        var f = l.match(/^ {5}(\S+)\s+(.+)$/);
        if (f) { feat = { type: f[1], location: f[2].trim(), q: {} }; rec.features.push(feat); qual = null; continue; }
        if (!feat) continue;
        var body = l.replace(/^\s{21}/, '');
        var qm = body.match(/^\/([^=\s]+)(?:=(.*))?$/);
        if (qm) {
          qual = qm[1];
          var v = qm[2] === undefined ? '' : qm[2];
          feat.q[qual] = (feat.q[qual] === undefined ? '' : feat.q[qual] + ' ') + v;
          feat.open = qual;
        } else if (qual) {
          feat.q[qual] += (/^\w/.test(body) && /\w$/.test(feat.q[qual]) ? ' ' : ' ') + body.trim();
        }
        // join the location when it continues on the next line
        if (!qm && !qual && feat) feat.location += body.trim();
      }
      rec.features.forEach(function(ft){
        Object.keys(ft.q).forEach(function(k){
          var v = ft.q[k].trim();
          if (/^".*"$/s.test(v)) v = v.slice(1, -1).replace(/""/g, '"');
          ft.q[k] = v;
        });
        delete ft.open;
      });
    }
    var seq = [], inSeq = false;
    for (; i < lines.length; i++) {
      if (/^ORIGIN/.test(lines[i])) { inSeq = true; continue; }
      if (/^\/\//.test(lines[i])) break;
      if (inSeq) seq.push(lines[i].replace(/[^A-Za-z]/g, ''));
    }
    rec.sequence = seq.join('').toLowerCase();
    return rec;
  }

  /* ---- SBOL 3 writing ---- */
  function roleFor(ft){
    var label = ft.q.label || ft.q.gene || '';
    if (/^(BbsI|BsaI|SapI|EcoRI|XbaI|SpeI|PstI|NotI)$/i.test(label.trim())) return SITE_ROLE;
    return ROLE[ft.type] || ROLE.misc_feature;
  }
  function fromGenbank(text, options){
    options = options || {};
    var records = splitRecords(text).map(parseRecord).filter(function(r){ return r.sequence.length; });
    var used = {}, out = [];
    out.push('@prefix sbol: <http://sbols.org/v3#> .');
    out.push('@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .');
    out.push('@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .');
    out.push('');
    records.forEach(function(rec){
      var id = displayId(rec.name, used), comp = NS + id, seq = NS + id + '_seq';
      var L = [];
      L.push('<' + comp + '> a sbol:Component ;');
      L.push('  sbol:displayId ' + lit(id) + ' ;');
      L.push('  sbol:hasNamespace <' + NS.replace(/\/$/, '') + '> ;');
      L.push('  sbol:name ' + lit(rec.name) + ' ;');
      if (rec.definition) L.push('  sbol:description ' + lit(rec.definition) + ' ;');
      L.push('  sbol:type <https://identifiers.org/SBO:0000251>, <' + SO + (rec.circular ? '0000988' : '0000987') + '> ;');
      L.push('  sbol:role <' + SO + (rec.circular ? '0000637' : '0000804') + '> ;');
      L.push('  sbol:hasSequence <' + seq + '>');
      var featIds = rec.features.map(function(ft, k){ return NS + id + '/feature' + (k + 1); });
      featIds.forEach(function(f){ L[L.length - 1] += ' ;'; L.push('  sbol:hasFeature <' + f + '>'); });
      L[L.length - 1] += ' .';
      L.push('');
      L.push('<' + seq + '> a sbol:Sequence ;');
      L.push('  sbol:displayId ' + lit(id + '_seq') + ' ;');
      L.push('  sbol:hasNamespace <' + NS.replace(/\/$/, '') + '> ;');
      L.push('  sbol:encoding <https://identifiers.org/edam:format_1207> ;');
      L.push('  sbol:elements ' + lit(rec.sequence) + ' .');
      L.push('');
      rec.features.forEach(function(ft, k){
        var fid = featIds[k], ranges = parseLocation(ft.location);
        if (!ranges.length) return;
        var label = stripTags(ft.q.label || ft.q.gene || ft.type);
        var desc = [ft.q.note, ft.q.product].filter(Boolean).map(stripTags).join('. ');
        var locs = ranges.map(function(r, j){ return fid + '/location' + (j + 1); });
        L.push('<' + fid + '> a sbol:SequenceFeature ;');
        L.push('  sbol:displayId ' + lit('feature' + (k + 1)) + ' ;');
        L.push('  sbol:name ' + lit(label) + ' ;');
        if (desc) L.push('  sbol:description ' + lit(desc) + ' ;');
        L.push('  sbol:role <' + SO + roleFor(ft) + '> ;');
        locs.forEach(function(l, j){ L.push('  sbol:hasLocation <' + l + '>' + (j < locs.length - 1 ? ' ;' : ' .')); });
        L.push('');
        ranges.forEach(function(r, j){
          L.push('<' + locs[j] + '> a sbol:Range ;');
          L.push('  sbol:displayId ' + lit('location' + (j + 1)) + ' ;');
          L.push('  sbol:hasSequence <' + seq + '> ;');
          L.push('  sbol:start ' + r.start + ' ;');
          L.push('  sbol:end ' + r.end + ' ;');
          L.push('  sbol:orientation <' + SO + (r.reverse ? '0001031' : '0001030') + '> .');
          L.push('');
        });
      });
      out.push(L.join('\n'));
    });
    return out.join('\n');
  }

  var api = { fromGenbank: fromGenbank, parseRecord: parseRecord, splitRecords: splitRecords, parseLocation: parseLocation };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ENCORE_SBOL = api;
})(typeof window !== 'undefined' ? window : this);
