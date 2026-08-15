<?php
/**
 * Plugin Name: Daily Flare SEO Toolkit
 * Description: Accurate, read-only SEO diagnostics and reporting for The Daily Flare.
 * Version: 2.2.0
 * Author: The Daily Flare
 * License: GPL-2.0-or-later
 * Requires at least: 6.2
 * Requires PHP: 7.4
 */
if (!defined('ABSPATH')) exit;

final class DF_SEO_Toolkit_V2 {
    const VERSION='2.2.0', OPT='df_seo_toolkit_v2_report', MENU='daily-flare-seo-v2';

    public static function init(){
        add_action('admin_menu',[__CLASS__,'menu']);
        add_action('admin_post_df_seo_v2_audit',[__CLASS__,'audit_action']);
        add_action('rest_api_init',[__CLASS__,'rest']);
        add_action('init',[__CLASS__,'abilities'],20);
    }
    private static function site(){return untrailingslashit(home_url('/'));}
    private static function get($url){
        $r=wp_remote_get($url,['timeout'=>20,'redirection'=>8,'user-agent'=>'DailyFlareSEOToolkit/'.self::VERSION.' (+'.self::site().')']);
        if(is_wp_error($r)) return ['status'=>0,'url'=>$url,'final'=>$url,'type'=>'','body'=>'','robots'=>'','error'=>$r->get_error_message()];
        return ['status'=>(int)wp_remote_retrieve_response_code($r),'url'=>$url,'final'=>$url,'type'=>(string)wp_remote_retrieve_header($r,'content-type'),'body'=>wp_remote_retrieve_body($r),'robots'=>(string)wp_remote_retrieve_header($r,'x-robots-tag')];
    }
    private static function same_host($url){return strtolower((string)parse_url($url,PHP_URL_HOST))===strtolower((string)parse_url(self::site(),PHP_URL_HOST));}
    private static function absolute($url){
        $url=trim($url); if(!$url)return '';
        if(stripos($url,'//')===0)return (is_ssl()?'https:':'http:').$url;
        if(strpos($url,'http://')===0||strpos($url,'https://')===0)return $url;
        return self::site().'/'.ltrim($url,'/');
    }
    private static function sitemap_urls($limit){
        $found=[];$checked=[];$queue=[self::site().'/sitemap.xml',self::site().'/sitemap_index.xml',self::site().'/wp-sitemap.xml'];
        while($queue&&count($found)<$limit&&count($checked)<30){
            $map=array_shift($queue);if(isset($checked[$map]))continue;$checked[$map]=1;$r=self::get($map);if($r['status']!==200)continue;
            preg_match_all('/<loc>\s*([^<]+)\s*<\/loc>/i',$r['body'],$m);
            foreach($m[1] as $loc){$u=esc_url_raw(html_entity_decode(trim($loc)));if(!$u||!self::same_host($u))continue;$path=strtolower((string)parse_url($u,PHP_URL_PATH));if(substr($path,-4)==='.xml')$queue[]=$u;else$found[]=$u;}
        }
        return array_values(array_unique(array_slice($found,0,$limit)));
    }
    private static function issue($id,$severity,$message){return ['id'=>$id,'severity'=>$severity,'message'=>$message];}
    private static function audit_page($url){
        $r=self::get($url);$p=['url'=>$url,'status'=>$r['status'],'final_url'=>$r['final'],'issues'=>[],'links'=>[],'images'=>[],'title'=>'','description'=>'','canonical'=>'','robots'=>'','h1_count'=>0];
        if($r['status']!==200){$sev=($r['status']>=500||$r['status']===404)?'critical':'warning';$p['issues'][]=self::issue('http',$sev,'Page returned HTTP '.$r['status'].'.');return $p;}
        if(stripos($r['type'],'html')===false){$p['issues'][]=self::issue('non-html','warning','URL returned HTTP 200 but is not HTML.');return $p;}
        libxml_use_internal_errors(true);$d=new DOMDocument();@$d->loadHTML('<?xml encoding="UTF-8">'.$r['body']);$x=new DOMXPath($d);
        $p['title']=trim($x->evaluate('string(//title)'));
        $p['description']=trim($x->evaluate('string(//meta[translate(@name,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz")="description"]/@content)'));
        $p['canonical']=trim($x->evaluate('string(//link[contains(concat(" ",normalize-space(@rel)," ")," canonical ")]/@href)'));
        $p['robots']=trim($x->evaluate('string(//meta[translate(@name,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz")="robots"]/@content)'));
        $p['canonical_absolute']=$p['canonical']?self::absolute($p['canonical']):'';
        $h=$x->query('//h1');$p['h1_count']=$h->length;
        if(!$p['title'])$p['issues'][]=self::issue('missing-title','critical','Missing <title>.');elseif(strlen($p['title'])<30||strlen($p['title'])>65)$p['issues'][]=self::issue('title-length','warning','Title is outside the recommended 30–65 character range.');
        if(!$p['description'])$p['issues'][]=self::issue('missing-description','warning','Missing meta description.');elseif(strlen($p['description'])<70||strlen($p['description'])>165)$p['issues'][]=self::issue('description-length','notice','Meta description is outside the recommended 70–165 character range.');
        if(!$p['canonical'])$p['issues'][]=self::issue('missing-canonical','critical','Missing canonical link.');elseif(!self::same_host($p['canonical_absolute']))$p['issues'][]=self::issue('canonical-external','warning','Canonical points to a different host.');
        if($p['h1_count']===0)$p['issues'][]=self::issue('missing-h1','warning','No H1 found.');elseif($p['h1_count']>1)$p['issues'][]=self::issue('multiple-h1','notice','Multiple H1 elements found.');
        if(stripos($p['robots'],'noindex')!==false)$p['issues'][]=self::issue('noindex','critical','Page contains a noindex directive.');
        foreach($x->query('//img') as $img){
            $src=trim($img->getAttribute('src'));if(!$src)$src=trim($img->getAttribute('data-src'));$alt=$img->hasAttribute('alt')?$img->getAttribute('alt'):null;$full=self::absolute($src);$path=parse_url($full,PHP_URL_PATH)?:'';$name=pathinfo($path,PATHINFO_FILENAME);$generic=(bool)preg_match('/^(image|img|photo|picture|file|wp|dsc|pxl)[_-]?[0-9a-z_-]{4,}$|^[0-9]{5,}$/i',$name);$alt_issue=$alt===null?'missing-alt':(trim($alt)===''?'empty-alt':null);if($alt_issue||$generic)$p['images'][]=['src'=>$full,'alt'=>$alt,'filename'=>$name,'alt_issue'=>$alt_issue,'filename_issue'=>$generic?'generic-or-generated':null];
        }
        foreach($x->query('//a[@href]') as $a){$href=trim($a->getAttribute('href'));if(!$href||$href[0]==='#'||stripos($href,'mailto:')===0||stripos($href,'tel:')===0||stripos($href,'javascript:')===0)continue;$u=self::absolute($href);if(self::same_host($u))$p['links'][]=untrailingslashit(esc_url_raw($u));}
        $p['links']=array_values(array_unique($p['links']));$p['image_issue_count']=count($p['images']);return $p;
    }
    private static function score($pages,$index){
        if(!$pages)return 0;$sum=0;
        foreach($pages as $p){$pen=0;foreach($p['issues'] as $i)$pen+=['critical'=>20,'warning'=>6,'notice'=>2][$i['severity']]??0;$sum+=max(0,100-min(100,$pen));}
        $score=$sum/count($pages);
        foreach($index['findings'] as $f)$score-=($f['severity']==='critical'?3:1);
        return max(0,min(100,(int)round($score)));
    }
    public static function run($limit=100){
        $limit=max(1,min(500,(int)$limit));$urls=self::sitemap_urls($limit);$source='sitemap';
        if(!$urls){$source='wordpress';$q=new WP_Query(['post_type'=>['post','page'],'post_status'=>'publish','posts_per_page'=>$limit,'fields'=>'ids']);foreach($q->posts as $id){$u=get_permalink($id);if($u)$urls[]=$u;}}
        if(!$urls)$urls=[self::site().'/'];$pages=[];foreach(array_values(array_unique($urls)) as $u)$pages[]=self::audit_page($u);
        $audited=[];$incoming=[];$titles=[];$descs=[];$images=0;$sev=['critical'=>0,'warning'=>0,'notice'=>0];$issue_counts=[];$image_counts=['missing-alt'=>0,'empty-alt'=>0,'generic-or-generated'=>0];
        foreach($pages as $p){$audited[untrailingslashit($p['url'])]=1;if($p['title'])$titles[strtolower(trim($p['title']))][]=$p['url'];if($p['description'])$descs[strtolower(trim($p['description']))][]=$p['url'];$images+=(int)$p['image_issue_count'];foreach($p['issues'] as $i){$sev[$i['severity']]++;$issue_counts[$i['id']]=($issue_counts[$i['id']]??0)+1;}foreach($p['images'] as $im){if($im['alt_issue'])$image_counts[$im['alt_issue']]++;if($im['filename_issue'])$image_counts[$im['filename_issue']]++;}foreach($p['links'] as $l)$incoming[untrailingslashit($l)]=($incoming[untrailingslashit($l)]??0)+1;}
        $dupt=[];foreach($titles as $v)if(count($v)>1)$dupt[]=$v;$dupd=[];foreach($descs as $v)if(count($v)>1)$dupd[]=$v;$unlinked=[];foreach($pages as $p){$u=untrailingslashit($p['url']);if($p['status']===200&&empty($incoming[$u]))$unlinked[]=$u;}
        $index=['checks'=>[],'findings'=>[]];foreach(['/robots.txt','/sitemap.xml','/sitemap_index.xml','/wp-sitemap.xml'] as $path){$r=self::get(self::site().$path);$index['checks'][$path]=['status'=>$r['status'],'final_url'=>$r['final'],'content_type'=>$r['type']];}
        if($index['checks']['/robots.txt']['status']!==200)$index['findings'][]=['severity'=>'warning','message'=>'robots.txt did not return HTTP 200.'];
        $sitemap_ok=$index['checks']['/sitemap.xml']['status']===200||$index['checks']['/sitemap_index.xml']['status']===200||$index['checks']['/wp-sitemap.xml']['status']===200;if(!$sitemap_ok)$index['findings'][]=['severity'=>'critical','message'=>'No supported sitemap endpoint returned HTTP 200.'];
        $host=[];$preferred=self::site();$www=preg_replace('#^https?://#','https://www.',$preferred);foreach(array_unique([$preferred,$www]) as $v){$r=self::get($v.'/');$host[]=['url'=>$v.'/','status'=>$r['status'],'final_url'=>$r['final']];}
        $index['host_variants']=$host;$index['preferred_host']=$preferred;
        $score=self::score($pages,$index);
        $report=['tool_version'=>self::VERSION,'site'=>self::site(),'generated_at'=>current_time('mysql'),'read_only'=>true,'score'=>$score,'score_method'=>'Per-page weighted score: critical -20, warning -6, notice -2; page penalties capped at 100. Indexing checks are separate.','crawl_source'=>$source,'pages_audited'=>count($pages),'severity_counts'=>$sev,'issue_counts'=>$issue_counts,'duplicate_titles'=>$dupt,'duplicate_descriptions'=>$dupd,'unlinked_within_audit'=>$unlinked,'image_issues'=>$images,'image_issue_breakdown'=>$image_counts,'indexing_readiness'=>$index,'pages'=>$pages];
        update_option(self::OPT,$report,false);return $report;
    }
    private static function report(){return get_option(self::OPT,[]);}
    public static function audit_action(){if(!current_user_can('manage_options'))wp_die('Unauthorized');check_admin_referer('df_seo_v2');self::run(isset($_POST['limit'])?$_POST['limit']:100);wp_safe_redirect(admin_url('admin.php?page='.self::MENU));exit;}
    public static function menu(){add_menu_page('Daily Flare SEO','Daily Flare SEO','manage_options',self::MENU,[__CLASS__,'dashboard'],'dashicons-chart-area',58);add_submenu_page(self::MENU,'Dashboard','Dashboard','manage_options',self::MENU,[__CLASS__,'dashboard']);add_submenu_page(self::MENU,'Findings','Findings','manage_options',self::MENU.'-findings',[__CLASS__,'findings']);}
    private static function css(){echo '<style>.df-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin:20px 0}.df-card{background:#fff;border:1px solid #dcdcde;border-radius:8px;padding:18px}.df-num{font-size:30px;font-weight:700}.df-muted{color:#646970}.df-critical{color:#b32d2e}.df-warning{color:#996800}.df-good{color:#008a20}.df-score{font-size:48px;font-weight:800}.df-table{width:100%;border-collapse:collapse;background:#fff}.df-table th,.df-table td{padding:10px;border-bottom:1px solid #eee;text-align:left}.df-help{background:#f6f7f7;border-left:4px solid #2271b1;padding:10px 14px}.df-empty{color:#008a20;font-weight:600}</style>';}
    private static function label($id){$map=['http'=>'HTTP status','missing-title'=>'Missing title','title-length'=>'Title length','missing-description'=>'Missing description','description-length'=>'Description length','missing-canonical'=>'Missing canonical','canonical-external'=>'External canonical','missing-h1'=>'Missing H1','multiple-h1'=>'Multiple H1','noindex'=>'Noindex','non-html'=>'Non-HTML URL'];return $map[$id]??ucwords(str_replace('-',' ',$id));}
    public static function dashboard(){
        if(!current_user_can('manage_options'))return;$r=self::report();self::css();echo '<div class="wrap"><h1>Daily Flare SEO Toolkit <span class="df-muted">v'.self::VERSION.'</span></h1><p>Read-only audit. No posts, media, URLs or indexing settings are changed.</p><form method="post" action="'.esc_url(admin_url('admin-post.php')).'">';wp_nonce_field('df_seo_v2');echo '<input type="hidden" name="action" value="df_seo_v2_audit"><label>Pages to audit <input type="number" name="limit" value="100" min="1" max="500" style="width:90px"></label> <button class="button button-primary">Run SEO Audit</button></form>';
        if(!$r){echo '<div class="notice notice-info"><p>No audit has been run yet.</p></div></div>';return;}$s=array_merge(['critical'=>0,'warning'=>0,'notice'=>0],$r['severity_counts']);echo '<div class="df-grid"><div class="df-card"><div class="df-muted">SEO score</div><div class="df-score">'.(int)$r['score'].'%</div><small>Weighted per page</small></div><div class="df-card"><div class="df-muted">Pages audited</div><div class="df-num">'.(int)$r['pages_audited'].'</div><small>Source: '.esc_html($r['crawl_source']).'</small></div><div class="df-card"><div class="df-muted">Critical</div><div class="df-num df-critical">'.(int)$s['critical'].'</div></div><div class="df-card"><div class="df-muted">Warnings</div><div class="df-num df-warning">'.(int)$s['warning'].'</div></div><div class="df-card"><div class="df-muted">Opportunities</div><div class="df-num">'.(int)$s['notice'].'</div></div><div class="df-card"><div class="df-muted">Image issues</div><div class="df-num">'.(int)$r['image_issues'].'</div></div></div>';
        echo '<div class="df-help"><strong>How to read this:</strong> HTTP 404/5xx, missing titles/canonicals and noindex are critical. Missing descriptions and title-length issues are warnings. Image metadata is an optimization queue. A 404 on an unused alternative sitemap endpoint is not automatically a failure when another sitemap works.</div><h2>Indexing & host checks</h2><table class="df-table"><tr><th>Check</th><th>Status</th><th>Result</th></tr>';foreach($r['indexing_readiness']['checks'] as $k=>$v)echo '<tr><td>'.esc_html($k).'</td><td>'.(int)$v['status'].'</td><td>'.esc_html($v['final_url']).'</td></tr>';foreach($r['indexing_readiness']['findings'] as $f)echo '<tr><td colspan="3"><strong class="df-warning">'.esc_html(strtoupper($f['severity'])).'</strong> '.esc_html($f['message']).'</td></tr>';echo '</table><h2>Issue summary</h2><table class="df-table"><tr><th>Finding</th><th>Count</th></tr>';foreach($r['issue_counts'] as $k=>$v)echo '<tr><td>'.esc_html(self::label($k)).'</td><td>'.(int)$v.'</td></tr>';echo '</table><h2>Image issue breakdown</h2><table class="df-table"><tr><th>Image issue</th><th>Count</th></tr>';foreach($r['image_issue_breakdown'] as $k=>$v)echo '<tr><td>'.esc_html(ucwords(str_replace('-',' ',$k))).'</td><td>'.(int)$v.'</td></tr>';echo '</table><p class="df-muted">Generated '.esc_html($r['generated_at']).'.</p></div>';
    }
    public static function findings(){if(!current_user_can('manage_options'))return;$r=self::report();self::css();echo '<div class="wrap"><h1>SEO Findings</h1>';if(!$r){echo '<p>Run an audit first.</p></div>';return;}foreach([['duplicate_titles','Duplicate titles'],['duplicate_descriptions','Duplicate descriptions'],['unlinked_within_audit','Pages with no incoming link inside the audited set']] as $row){echo '<h2>'.esc_html($row[1]).' <span class="df-muted">('.count($r[$row[0]]).')</span></h2>';if(!$r[$row[0]])echo '<p class="df-empty">None found.</p>';else echo '<pre style="background:#fff;padding:15px;overflow:auto;max-height:400px">'.esc_html(wp_json_encode($r[$row[0]],JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES)).'</pre>';}echo '<h2>Page-level details</h2><pre style="background:#fff;padding:15px;overflow:auto;max-height:700px">'.esc_html(wp_json_encode($r['pages'],JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES)).'</pre></div>';}
    public static function rest(){register_rest_route('daily-flare/v1','/seo/report',['methods'=>'GET','permission_callback'=>function(){return current_user_can('manage_options');},'callback'=>function(){return rest_ensure_response(self::report());}]);register_rest_route('daily-flare/v1','/seo/audit',['methods'=>'POST','permission_callback'=>function(){return current_user_can('manage_options');},'callback'=>function($req){return rest_ensure_response(self::run((int)($req->get_param('limit')?:100)));}]);}
    public static function abilities(){
        if(!function_exists('wp_register_ability'))return;
        try{wp_register_ability('dailyflare/seo-report',['label'=>'Daily Flare SEO Report','description'=>'Return the latest read-only Daily Flare SEO report.','input_schema'=>['type'=>'object','properties'=>[],'additionalProperties'=>false],'output_schema'=>['type'=>'object'],'execute_callback'=>function(){return self::report();},'permission_callback'=>function(){return current_user_can('manage_options');}]);}catch(Throwable $e){}
        try{wp_register_ability('dailyflare/seo-audit',['label'=>'Run Daily Flare SEO Audit','description'=>'Run a read-only SEO audit.','input_schema'=>['type'=>'object','properties'=>['limit'=>['type'=>'integer','minimum'=>1,'maximum'=>500]],'additionalProperties'=>false],'output_schema'=>['type'=>'object'],'execute_callback'=>function($input){return self::run(isset($input['limit'])?(int)$input['limit']:100);},'permission_callback'=>function(){return current_user_can('manage_options');}]);}catch(Throwable $e){}
    }
}
DF_SEO_Toolkit_V2::init();
